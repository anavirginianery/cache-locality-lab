#!/usr/bin/env python3
"""
pipeline.py - amostragem das cargas geradas, organizada por FASE, com os scripts do cache-sampling.

Uma fase de amostragem le as cargas de UMA fase da geracao (a "origem"), converte cada carga
para o formato que o cache-sampling espera e roda sobre ela os scripts originais de
cache-sampling/sampling, sem modifica-los. O que sai sao as amostras, renomeadas para o padrao
deste laboratorio, e um resumo do que cada uma contem.

    fases/a01-temporal-f03/
      experimentos.json   a configuracao desta fase (fonte da verdade)
      manifesto.json      o que foi rodado, quando, com que codigo, e como saiu
      LEIAME.md           o que e cada arquivo da fase, nome a nome
      entrada/            trace_a01_baixa-b150.csv   (a carga no formato do cache-sampling)
      amostras/           amostra_a01_baixa-b150_sis-p10.csv ...
      analise/            amostras_a01.csv

    1. conversao   carga_f03_*.txt (um id por linha) -> ts,id,tamanho sem cabecalho -> entrada/
    2. amostragem  systematic_sampling.sh e window_sampling.sh              -> amostras/
    3. resumo      linhas, fracao real, objetos distintos e blocos          -> analise/
    4. analise     as medidas da geracao (lib/medidas.py) em cada amostra   -> analise/
                   e na carga completa: stack distance, curva de hit LRU,
                   footprint e frequencia por objeto
    5. graficos    um SVG por metrica, em facetas: tecnica x nivel de SD   -> analise/

Uso:
    python3 pipeline.py --nova-fase temporal-f03   # cria a fase a partir do modelo e para
    python3 pipeline.py --fase a01                 # roda a fase (aceita id ou nome da pasta)
    python3 pipeline.py --fase a01 --so-analise    # nao reamostra, so remede
    python3 pipeline.py --fases                    # lista as fases ja rodadas

Nomes das amostras: amostra_<fase>_<cenario>_<metodo>.csv, com o metodo escrito como
sis-p10 (sistematica, 10%) ou jan-p10-t1k (janela, 10%, ultimas 1.000 linhas de cada janela).
A taxa entra em pontos percentuais com dois digitos, para os arquivos ordenarem num `ls`.
"""
import argparse, csv, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import genwl
import medidas
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graficos

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
FASES = os.path.join(AQUI, "fases")
FASES_GERACAO = os.path.join(RAIZ, "geracao", "fases")
MODELO = os.path.join(AQUI, "experimentos.json")
CODIGO = ("amostragem/pipeline.py", "amostragem/graficos.py", "lib/medidas.py", "lib/genwl.py")
SCRIPTS = ("systematic_sampling.sh", "window_sampling.sh")

# As taxas e as janelas estao fixas dentro dos scripts do cache-sampling; aqui so se registra
# quais sao, para nomear os arquivos e conferir o resultado. (rotulo do script, % , janela por take)
TAXAS = (("one", 1), ("ten", 10), ("twenty", 20))
JANELAS = {1000: {1: 100000, 10: 10000, 20: 5000},
           10000: {1: 1000000, 10: 100000, 20: 50000}}
METODOS = {"sistematica": None, "janela-1k": 1000, "janela-10k": 10000}   # nome -> take


def curto(metodo, pct):
    """Trecho do nome do arquivo: sis-p10, jan-p10-t1k."""
    take = METODOS[metodo]
    if take is None:
        return "sis-p%02d" % pct
    return "jan-p%02d-t%dk" % (pct, take // 1000)


def tipo_cache_sampling(metodo, pct):
    """O nome que o mesmo tipo de amostra tem no cache-sampling (trace_type do results.csv)."""
    rot = dict((p, r) for r, p in TAXAS)[pct]
    take = METODOS[metodo]
    return "systematic_%s" % rot if take is None else "window_%s_%dk" % (rot, take // 1000)


# --------------------------------------------------------------- fases
def id_da_pasta(pasta):
    return pasta.split("-")[0]


def lista_fases(base=FASES, letra="a"):
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)) and re.match(r"^%s\d+" % letra, d))


def acha_fase(arg, base=FASES, letra="a"):
    fases = lista_fases(base, letra)
    if arg in fases:
        return os.path.join(base, arg)
    iguais = [d for d in fases if id_da_pasta(d) == arg]
    if len(iguais) == 1:
        return os.path.join(base, iguais[0])
    raise SystemExit("fase %r nao encontrada em %s. Fases: %s"
                     % (arg, os.path.relpath(base, RAIZ), ", ".join(fases) or "nenhuma"))


def nova_fase(apelido):
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", apelido):
        raise SystemExit("apelido so com minusculas, numeros e hifen; recebi %r" % apelido)
    usados = [int(id_da_pasta(d)[1:]) for d in lista_fases()]
    aid = "a%02d" % (max(usados) + 1 if usados else 1)
    pasta = os.path.join(FASES, "%s-%s" % (aid, apelido))
    for sub in ("entrada", "amostras", "analise"):
        os.makedirs(os.path.join(pasta, sub), exist_ok=True)
    destino = os.path.join(pasta, "experimentos.json")
    if not os.path.exists(destino):
        shutil.copy(MODELO, destino)
    print("fase criada: %s" % os.path.relpath(pasta, AQUI))
    print("  1. edite   %s" % os.path.relpath(destino, AQUI))
    print("  2. rode    python3 pipeline.py --fase %s" % aid)


def valida(cfg, aid):
    e = []
    for k in ("origem", "aquecimento", "scripts", "metodos"):
        if k not in cfg:
            e.append("falta o campo %s" % k)
    if not e:
        if cfg["aquecimento"] not in ("descartar", "manter"):
            e.append("aquecimento: 'descartar' ou 'manter'; veio %r" % cfg["aquecimento"])
        ruins = [m for m in cfg["metodos"] if m not in METODOS]
        if ruins or not cfg["metodos"]:
            e.append("metodos: escolha entre %s; veio %r" % (", ".join(METODOS), cfg["metodos"]))
        scripts = os.path.join(RAIZ, cfg["scripts"])
        faltam = [s for s in SCRIPTS if not os.path.isfile(os.path.join(scripts, s))]
        if faltam:
            e.append("scripts: %s nao tem %s" % (scripts, ", ".join(faltam)))
    if e:
        raise SystemExit("experimentos.json da fase %s:\n  - %s" % (aid, "\n  - ".join(e)))


def sha(caminho, n=12):
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:n]


def info_git():
    def roda(*args):
        try:
            r = subprocess.run(args, cwd=AQUI, capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""
    commit = roda("git", "rev-parse", "--short", "HEAD")
    if not commit:
        return {"commit": None, "limpo": None, "git_disponivel": False}
    return {"commit": commit, "limpo": roda("git", "status", "--porcelain", "--", RAIZ) == "",
            "git_disponivel": True}


# --------------------------------------------------------------- etapa 1
def etapa_conversao(carga, destino, dmax, aquecimento):
    """Uma linha 'ts,id,1' por requisicao, sem cabecalho: o formato de saida do preprocessing
    do cache-sampling (timestamp, item remapeado, tamanho), que e o que o simulador le.

    O ts e a posicao da requisicao na carga (0, 1, 2, ...). Ele nao muda de valor na amostra,
    entao cada linha amostrada continua dizendo de onde veio. O tamanho e 1: o simulador conta
    o cache em objetos e ignora essa coluna."""
    with open(carga) as fh:
        ids = [l.strip() for l in fh if l.strip()]
    esperado = [str(k) for k in range(dmax - 1, -1, -1)]
    if ids[:dmax] != esperado:
        raise SystemExit("%s: as %d primeiras linhas nao sao o prefixo de aquecimento esperado "
                         "(%d, %d, ..., 0)" % (carga, dmax, dmax - 1, dmax - 2))
    if aquecimento == "descartar":
        ids = ids[dmax:]
    with open(destino, "w") as out:
        out.write("".join("%d,%s,1\n" % (i, o) for i, o in enumerate(ids)))
    return len(ids)


# --------------------------------------------------------------- etapa 2
def etapa_amostragem(scripts, metodo, suf, entrada, tmp):
    """Roda o script original num diretorio limpo e devolve {pct: caminho da amostra}.

    O diretorio precisa estar vazio: o window_sampling.sh escreve com '>>' e, rodado duas vezes
    no mesmo lugar, duplicaria a amostra."""
    shutil.rmtree(tmp, ignore_errors=True)
    dirs = [os.path.join(tmp, rot) for rot, _ in TAXAS]
    take = METODOS[metodo]
    if take is None:
        cmd = ["bash", os.path.join(scripts, "systematic_sampling.sh"), suf, entrada] + dirs
        nomes = ["trace_%s_%s.csv" % (suf, rot) for rot, _ in TAXAS]
    else:
        cmd = ["bash", os.path.join(scripts, "window_sampling.sh"), suf, entrada, str(take)] + dirs
        nomes = ["sample_%s.csv" % suf] * len(TAXAS)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("%s falhou:\n%s%s" % (" ".join(cmd), r.stdout, r.stderr))
    return {pct: os.path.join(d, n) for (_, pct), d, n in zip(TAXAS, dirs, nomes)}


# --------------------------------------------------------------- etapa 3
def etapa_resumo(caminho, total):
    """Mede a amostra: quantas linhas, que fracao da entrada, quantos objetos distintos, e em
    quantos blocos de linhas consecutivas da carga ela se divide (1 bloco = um trecho continuo)."""
    ts, objs = [], set()
    with open(caminho) as fh:
        for l in fh:
            t, o, _ = l.rstrip("\n").split(",", 2)
            ts.append(int(t))
            objs.add(o)
    blocos = sum(1 for i, t in enumerate(ts) if i == 0 or t != ts[i - 1] + 1)
    return {"linhas": len(ts), "fracao": len(ts) / total, "distintos": len(objs),
            "blocos": blocos, "ts_primeiro": ts[0] if ts else None,
            "ts_ultimo": ts[-1] if ts else None}


# --------------------------------------------------------------- etapa 4
def le_ids(caminho):
    """Os ids de um arquivo ts,id,tamanho, na ordem."""
    with open(caminho) as fh:
        return [l.split(",", 2)[1] for l in fh]


def etapa_analise(orig, cen, entrada, amostras, dmax, caches):
    """Mede a carga completa e cada amostra com o mesmo instrumento da geracao (lib/medidas.py).

    Tudo e medido como um simulador veria o arquivo: comecando com o cache vazio, sem descartar
    nada (prefixo 0). A curva de hit usa os MESMOS tamanhos absolutos de cache na amostra e na
    carga completa, como faz o cache-sampling, e o erro de cada amostra e contra a completa.
    A teoria, que sai da distribuicao da fase de origem, vai junto como terceira referencia.

    Devolve [(rotulo, info, medida)], com a completa primeiro, e a grade de caches."""
    pmf, p_inf = genwl.load_sd_file(os.path.join(orig, cen["arquivos"]["dist"]))
    t_hit, _ = medidas.teoria(pmf, p_inf)
    ids = le_ids(entrada)
    grade = sorted(set(medidas.grade_log(len(ids))) | {dmax} | set(caches))
    saida = [("completa", {"metodo": "completa", "taxa_pct": 100, "take": None},
              medidas.medir(ids))]
    for a in amostras:
        saida.append((a["rotulo"], a, medidas.medir(le_ids(a["caminho"]))))
    return saida, grade, t_hit


def grava_analise(analise, aid, medidos, dmax):
    """Os mesmos CSVs da geracao, com uma coluna 'amostra' (completa, sis-p10, jan-p10-t1k...)."""
    escritos = []

    def w(nome, cab, linhas):
        arq = os.path.join(analise, "%s_%s.csv" % (nome, aid))
        with open(arq, "w", newline="") as fh:
            c = csv.writer(fh); c.writerow(cab); c.writerows(linhas)
        escritos.append(os.path.basename(arq))

    tudo = [(suf, rot, info, m, grade, t_hit, lista[0][2])
            for suf, (lista, grade, t_hit) in medidos
            for rot, info, m in lista]

    def erro_max(m, ref, grade):
        return max(abs(m["hit"](C) - ref["hit"](C)) for C in grade)

    def erro_medio(m, ref, grade):
        """Media do erro absoluto nos pontos da grade. A grade e logaritmica, entao cada decada
        de tamanho de cache pesa o mesmo na media."""
        return sum(abs(m["hit"](C) - ref["hit"](C)) for C in grade) / len(grade)

    def cache_do_erro_max(m, ref, grade):
        return max(grade, key=lambda C: abs(m["hit"](C) - ref["hit"](C)))

    w("medidas",
      ["cenario", "amostra", "metodo", "taxa_pct", "take", "requisicoes", "reusos", "p_inf_medido",
       "sd_p25", "sd_p50", "sd_p75", "sd_p90", "sd_p99", "sd_max", "objetos_distintos",
       "footprint_1000req", "req_por_objeto_media", "req_por_objeto_maxima",
       "fracao_objetos_1_req", "fracao_req_top1pct", "fracao_req_top10pct",
       "erro_max_hrc_vs_completa", "cache_do_erro_max", "erro_medio_abs_hrc_vs_completa"],
      [[suf, rot, info["metodo"], info["taxa_pct"], info["take"] or "", m["requisicoes"],
        m["reusos"], "%.5f" % m["p_inf_medido"], m["p25"], m["p50"], m["p75"], m["p90"], m["p99"],
        m["sd_max"], m["distintos"], round(m["fp_1k"], 1) if m["fp_1k"] else "",
        "%.2f" % m["freq"]["media"], m["freq"]["maxima"], "%.5f" % m["freq"]["um_hit"],
        "%.5f" % m["freq"]["top1"], "%.5f" % m["freq"]["top10"],
        "%.5f" % erro_max(m, ref, grade), cache_do_erro_max(m, ref, grade),
        "%.5f" % erro_medio(m, ref, grade)] for suf, rot, info, m, grade, t, ref in tudo])

    w("hrc", ["cenario", "amostra", "cache_objetos", "hit_teorico", "hit_completa", "hit_amostra",
              "erro_vs_completa"],
      [[suf, rot, C, "%.5f" % t(C), "%.5f" % ref["hit"](C), "%.5f" % m["hit"](C),
        "%.5f" % (m["hit"](C) - ref["hit"](C))]
       for suf, rot, info, m, grade, t, ref in tudo for C in grade])

    w("sd_cdf", ["cenario", "amostra", "d", "P(d<x)_completa", "P(d<x)_amostra"],
      [[suf, rot, x, "%.5f" % ref["cdf"](x), "%.5f" % m["cdf"](x)]
       for suf, rot, info, m, grade, t, ref in tudo for x in grade])

    w("sd_histograma", ["cenario", "amostra", "faixa_de", "faixa_ate", "reusos", "fracao"],
      [[suf, rot, a, b, c, "%.5f" % f] for suf, rot, info, m, *_ in tudo for a, b, c, f in m["hist"]])

    w("footprint", ["cenario", "amostra", "janela_requisicoes", "objetos_distintos_media",
                    "fracao_da_janela"],
      [[suf, rot, j, "%.1f" % x, "%.4f" % f] for suf, rot, info, m, *_ in tudo for j, x, f in m["fp"]])

    w("frequencia", ["cenario", "amostra", "rank", "requisicoes_ao_objeto",
                     "fracao_acumulada_das_requisicoes"],
      [[suf, rot, k, c, "%.5f" % a] for suf, rot, info, m, *_ in tudo for k, c, a in m["freq"]["curva"]])

    w("frequencia_hist", ["cenario", "amostra", "de", "ate", "objetos", "fracao_dos_objetos"],
      [[suf, rot, a, b, c, "%.5f" % f] for suf, rot, info, m, *_ in tudo for a, b, c, f in m["freq"]["hist"]])
    return escritos


# --------------------------------------------------------------- saidas
def assinatura(cfg, cargas_sha):
    return {"origem": cfg["origem"], "aquecimento": cfg["aquecimento"],
            "metodos": list(cfg["metodos"]), "cargas_sha": cargas_sha}


def escreve_leiame(pasta, aid, cfg, origem, linhas):
    txt = ["# Fase %s de amostragem" % aid, "",
           cfg.get("descricao", ""), "",
           "Gerado por `amostragem/pipeline.py`; nao edite a mao.", "",
           "- **Origem:** fase `%s` da geracao (`%s`)" % (cfg["origem"], origem),
           "- **Aquecimento:** %s as primeiras `dmax` linhas de cada carga antes de amostrar" % cfg["aquecimento"],
           "- **Scripts:** `%s` (sem modificacao)" % cfg["scripts"], "",
           "## Como ler os nomes", "",
           "`amostra_<fase>_<cenario>_<metodo>.csv`, por exemplo `amostra_%s_baixa-b150_jan-p10-t1k.csv`:" % aid, "",
           "| Trecho | Significado |", "|---|---|",
           "| `%s` | esta fase de amostragem (a origem esta no manifesto) |" % aid,
           "| `baixa-b150` | cenario da carga de origem: nivel de SD e beta x100 (1,5) |",
           "| `sis-p10` | amostragem **sistematica**, 10%: uma linha a cada 10 |",
           "| `jan-p10-t1k` | amostragem por **janela**, 10%: as ultimas 1.000 linhas de cada janela de 10.000 |", "",
           "Todo arquivo de `entrada/` e `amostras/` tem uma linha por requisicao, `ts,id,tamanho`, "
           "sem cabecalho. O `ts` e a posicao da requisicao na carga (sem o aquecimento, se ele foi "
           "descartado), entao numa amostra ele mostra de onde cada linha veio. O tamanho e sempre 1.", "",
           "## Arquivos", "",
           "| Arquivo | Metodo | Taxa | Janela | Take | Tipo no cache-sampling | Linhas | Blocos |",
           "|---|---|---|---|---|---|---|---|"]
    for l in linhas:
        txt.append("| `%s` | %s | %d%% | %s | %s | `%s` | %s | %d |" % (
            l["arquivo"], l["metodo"], l["taxa_pct"], l["janela"] or "-", l["take"] or "-",
            l["tipo_cache_sampling"], format(l["linhas"], ",").replace(",", "."), l["blocos"]))
    txt += ["", "Em `analise/`: `amostras_%s.csv` e o inventario acima, completo; os demais CSVs sao as "
            "medidas da geracao (stack distance, curva de hit, footprint, frequencia) aplicadas a "
            "carga completa (`amostra = completa`) e a cada amostra. Ver `amostragem/README.md`." % aid, ""]
    with open(os.path.join(pasta, "LEIAME.md"), "w") as fh:
        fh.write("\n".join(txt))


def escreve_index():
    linhas = []
    for d in lista_fases():
        cam = os.path.join(FASES, d, "manifesto.json")
        if not os.path.exists(cam):
            continue
        m = json.load(open(cam))
        linhas.append("| [%s](%s/) | %s | %s | %s | %s | %s | %d |" % (
            m["fase"], d, m["apelido"], m["gerado_em"][:10], m["origem"], m["aquecimento"],
            " / ".join(m["metodos"]), sum(len(c["amostras"]) for c in m["cenarios"])))
    txt = ["# Fases de amostragem", "",
           "Gerado por `pipeline.py`. Os detalhes de cada fase estao no `manifesto.json` e no",
           "`LEIAME.md` dentro da pasta.", "",
           "| Fase | Apelido | Data | Origem | Aquecimento | Metodos | Amostras |",
           "|---|---|---|---|---|---|---|"] + linhas + [""]
    with open(os.path.join(FASES, "INDEX.md"), "w") as fh:
        fh.write("\n".join(txt))


# --------------------------------------------------------------- fase
def roda_fase(pasta, refazer, so_analise=False):
    nome = os.path.basename(pasta)
    aid, apelido = id_da_pasta(nome), nome.split("-", 1)[-1]
    cfg = json.load(open(os.path.join(pasta, "experimentos.json")))
    valida(cfg, aid)
    scripts = os.path.join(RAIZ, cfg["scripts"])
    orig = acha_fase(cfg["origem"], FASES_GERACAO, "f")
    man_orig = json.load(open(os.path.join(orig, "manifesto.json")))
    dmax = man_orig["comum"]["dmax"]
    cenarios = man_orig["cenarios"]
    cargas_sha = {c["sufixo"]: sha(os.path.join(orig, c["arquivos"]["carga"])) for c in cenarios}

    man_path = os.path.join(pasta, "manifesto.json")
    if os.path.exists(man_path) and not refazer:
        antigo = json.load(open(man_path)).get("assinatura")
        if antigo != assinatura(cfg, cargas_sha):
            raise SystemExit(
                "a fase %s foi rodada com outra configuracao ou com outras cargas de origem "
                "(o experimentos.json mudou, ou a fase %s foi regerada).\n"
                "Rode com --refazer para sobrescrever, ou crie outra com --nova-fase."
                % (aid, cfg["origem"]))

    dirs = {d: os.path.join(pasta, d) for d in ("entrada", "amostras", "analise")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    tmp = os.path.join(pasta, ".tmp")
    print("== fase %s (%s) -- origem %s, aquecimento %s" % (aid, apelido, cfg["origem"], cfg["aquecimento"]))

    if so_analise:
        print("   (so analise: entrada/ e amostras/ nao foram refeitas)")
    caches = man_orig["comum"]["caches"]
    resumo, man_cen, medidos = [], [], []
    for cen in cenarios:
        suf = cen["sufixo"]
        carga = os.path.join(orig, cen["arquivos"]["carga"])
        entrada = os.path.join(dirs["entrada"], "trace_%s_%s.csv" % (aid, suf))
        if so_analise:
            if not os.path.exists(entrada):
                raise SystemExit("%s nao existe; rode sem --so-analise" % entrada)
            with open(entrada) as fh:
                total = sum(1 for _ in fh)
        else:
            total = etapa_conversao(carga, entrada, dmax, cfg["aquecimento"])
        print("   %s: %s linhas -> %s" % (suf, format(total, ","), os.path.relpath(entrada, pasta)))
        amostras, para_medir = [], []
        for metodo in cfg["metodos"]:
            brutos = {} if so_analise else etapa_amostragem(scripts, metodo, suf, entrada, tmp)
            for _, pct in TAXAS:
                arq = "amostra_%s_%s_%s.csv" % (aid, suf, curto(metodo, pct))
                caminho = os.path.join(dirs["amostras"], arq)
                if not so_analise:
                    shutil.move(brutos[pct], caminho)
                elif not os.path.exists(caminho):
                    raise SystemExit("%s nao existe; rode sem --so-analise" % caminho)
                r = etapa_resumo(caminho, total)
                take = METODOS[metodo]
                linha = dict(arquivo=arq, cenario=suf, beta=cen["beta"], metodo=metodo,
                             taxa_pct=pct, janela=JANELAS[take][pct] if take else None, take=take,
                             tipo_cache_sampling=tipo_cache_sampling(metodo, pct),
                             linhas_entrada=total, **r)
                resumo.append(linha)
                amostras.append({k: linha[k] for k in ("arquivo", "metodo", "taxa_pct", "janela",
                                                       "take", "tipo_cache_sampling", "linhas",
                                                       "distintos", "blocos")})
                para_medir.append(dict(linha, rotulo=curto(metodo, pct), caminho=caminho))
                print("      %-14s %8s linhas (%.2f%%)  %6s objetos  %4d bloco(s)"
                      % (curto(metodo, pct), format(r["linhas"], ","), 100 * r["fracao"],
                         format(r["distintos"], ","), r["blocos"]))
            shutil.rmtree(tmp, ignore_errors=True)
        lista, grade, t_hit = etapa_analise(orig, cen, entrada, para_medir, dmax, caches)
        medidos.append((suf, (lista, grade, t_hit)))
        ref = lista[0][2]
        print("      analise: SD mediana completa %d | erro max da curva de hit, por amostra: %s"
              % (ref["p50"], ", ".join("%s %.3f" % (rot, max(abs(m["hit"](C) - ref["hit"](C))
                                                            for C in grade))
                                         for rot, _, m in lista[1:])))
        for a in amostras:
            m = next(x for rot, i, x in lista if i is not None and i.get("arquivo") == a["arquivo"])
            a.update(sd_mediana=m["p50"], sd_p90=m["p90"],
                     erro_max_hrc_vs_completa=round(max(abs(m["hit"](C) - ref["hit"](C))
                                                        for C in grade), 5))
        man_cen.append({"nome": cen["nome"], "sufixo": suf, "beta": cen["beta"],
                        "carga_origem": os.path.relpath(carga, RAIZ), "carga_sha": cargas_sha[suf],
                        "entrada": os.path.relpath(entrada, pasta), "linhas_entrada": total,
                        "completa": {"sd_mediana": ref["p50"], "sd_p90": ref["p90"],
                                     "objetos_distintos": ref["distintos"]},
                        "amostras": amostras})

    campos = ["arquivo", "cenario", "beta", "metodo", "taxa_pct", "janela", "take",
              "tipo_cache_sampling", "linhas_entrada", "linhas", "fracao", "distintos",
              "blocos", "ts_primeiro", "ts_ultimo"]
    csv_path = os.path.join(dirs["analise"], "amostras_%s.csv" % aid)
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for l in resumo:
            w.writerow(dict(l, fracao="%.6f" % l["fracao"]))
    grava_analise(dirs["analise"], aid, medidos, dmax)

    man = {"fase": aid, "apelido": apelido, "descricao": cfg.get("descricao", ""),
           "gerado_em": datetime.now().isoformat(timespec="seconds"),
           "origem": cfg["origem"], "aquecimento": cfg["aquecimento"], "dmax_origem": dmax,
           "metodos": cfg["metodos"], "modo": "so-analise" if so_analise else "completo",
           "codigo": dict(info_git(), codigo_sha={c: sha(os.path.join(RAIZ, c)) for c in CODIGO},
                          scripts=cfg["scripts"],
                          scripts_sha={s: sha(os.path.join(scripts, s)) for s in SCRIPTS}),
           "assinatura": assinatura(cfg, cargas_sha),
           "cenarios": man_cen}
    with open(man_path, "w") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False)
    escreve_leiame(pasta, aid, cfg, os.path.basename(orig), resumo)
    escreve_index()
    graficos.gera(pasta)                           # le os CSVs e o manifesto recem-escritos
    print("\nresumo em %s | leia-me: %s" % (os.path.relpath(csv_path, AQUI),
                                          os.path.relpath(os.path.join(pasta, "LEIAME.md"), AQUI)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fase", help="id (a01) ou nome da pasta da fase a rodar")
    ap.add_argument("--nova-fase", metavar="APELIDO", help="cria uma fase nova a partir de experimentos.json")
    ap.add_argument("--fases", action="store_true", help="lista as fases ja rodadas")
    ap.add_argument("--so-analise", action="store_true", help="nao reconverte nem reamostra, so remede")
    ap.add_argument("--refazer", action="store_true",
                    help="sobrescreve a fase mesmo que a configuracao ou as cargas tenham mudado")
    a = ap.parse_args()
    if a.nova_fase:
        return nova_fase(a.nova_fase)
    if a.fases:
        cam = os.path.join(FASES, "INDEX.md")
        print(open(cam).read() if os.path.exists(cam) else "nenhuma fase rodada ainda")
        return
    if not a.fase:
        raise SystemExit("informe a fase: --fase <id>. Fases: %s" % (", ".join(lista_fases()) or "nenhuma"))
    roda_fase(acha_fase(a.fase), a.refazer, a.so_analise)


if __name__ == "__main__":
    main()
