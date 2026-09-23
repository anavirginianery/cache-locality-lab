#!/usr/bin/env python3
"""
pipeline.py - as tres etapas da geracao de carga, organizadas por FASE.

Uma fase e uma rodada de experimentacao: tudo o que e comum aos cenarios daquela rodada
(dmax, inf, requisicoes, semente, caches) mora no cenarios.json da fase. O que varia entre
os cenarios - hoje o beta - aparece no nome dos arquivos.

    fases/f01-linha-de-base/
      cenarios.json     a configuracao desta fase (fonte da verdade)
      manifesto.json    o que foi rodado, quando, em que commit, e como saiu
      dist/             sd_f01_baixa-b150.txt
      cargas/           carga_f01_baixa-b150.txt
      analise/          medidas_f01.csv ... relatorio_f01.html

    1. distribuicao   lei de potencia P(d) ~ (d+1)^-beta  ->  dist/
    2. carga          LRU Stack Model le a distribuicao   ->  cargas/
    3. conferencia    mede a carga e compara com a teoria ->  analise/

A curva usada nas analises e a de HIT RATE: hit(C) = fracao das requisicoes atendidas por um
cache LRU de C objetos. O miss e o complemento, 1 - hit. Tudo que a etapa 3 mede tem um valor
teorico calculado direto da distribuicao, entao o relatorio nao mostra so "o que deu": mostra
"o que deveria dar" ao lado.

Uso:
    python3 pipeline.py --nova-fase dmax-100k   # cria a fase a partir do modelo e para
    python3 pipeline.py --fase f02              # roda a fase (aceita id ou nome da pasta)
    python3 pipeline.py --fase f02 --so-analise # nao regera nada, so remede e redesenha
    python3 pipeline.py --fases                 # lista as fases ja rodadas

O beta entra no nome como inteiro de tres digitos, multiplicado por 100: beta 1,5 -> b150.
"""
import argparse, bisect, contextlib, csv, io, json, math, os, random, re, shutil, subprocess, sys
from datetime import datetime
from types import SimpleNamespace

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "lib"))   # genwl.py e mkps.py ficam em lib/
import genwl
import mkps

FASES = os.path.join(AQUI, "fases")
MODELO = os.path.join(AQUI, "cenarios.json")
COMUNS = ("dmax", "inf", "requisicoes", "semente", "caches", "tolerancia")
CORES = ["#63BDB5", "#2E9B95", "#08595C"]          # rampa ordinal: baixa -> alta
CORES_ESC = ["#16706C", "#2FA8A2", "#7FD6CF"]      # a mesma rampa no tema escuro


# --------------------------------------------------------------- fases
def sufixo(cen):
    """Nome curto do cenario, com o parametro que varia: baixa-b150 (beta 1,5)."""
    return "%s-b%03d" % (cen["nome"], round(cen["beta"] * 100))


def id_da_pasta(pasta):
    return pasta.split("-")[0]


def lista_fases():
    if not os.path.isdir(FASES):
        return []
    return sorted(d for d in os.listdir(FASES)
                  if os.path.isdir(os.path.join(FASES, d)) and re.match(r"^f\d+", d))


def nova_fase(apelido):
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", apelido):
        raise SystemExit("apelido so com minusculas, numeros e hifen; recebi %r" % apelido)
    usados = [int(id_da_pasta(d)[1:]) for d in lista_fases()]
    fid = "f%02d" % (max(usados) + 1 if usados else 1)
    pasta = os.path.join(FASES, "%s-%s" % (fid, apelido))
    for sub_ in ("dist", "cargas", "analise"):
        os.makedirs(os.path.join(pasta, sub_), exist_ok=True)
    destino = os.path.join(pasta, "cenarios.json")
    if not os.path.exists(destino):
        shutil.copy(MODELO, destino)
    print("fase criada: %s" % os.path.relpath(pasta, AQUI))
    print("  1. edite   %s" % os.path.relpath(destino, AQUI))
    print("  2. rode    python3 pipeline.py --fase %s" % fid)
    return pasta


def acha_fase(arg):
    fases = lista_fases()
    if not fases:
        raise SystemExit("nenhuma fase ainda; crie uma com --nova-fase <apelido>")
    if arg in fases:
        return os.path.join(FASES, arg)
    iguais = [d for d in fases if id_da_pasta(d) == arg]
    if len(iguais) == 1:
        return os.path.join(FASES, iguais[0])
    if len(iguais) > 1:
        raise SystemExit("mais de uma fase com o id %s: %s" % (arg, ", ".join(iguais)))
    raise SystemExit("fase %r nao encontrada. Fases: %s" % (arg, ", ".join(fases)))


def assinatura(cfg):
    """O que define a fase: os parametros comuns e a lista de cenarios."""
    return {"comum": {k: cfg[k] for k in COMUNS},
            "cenarios": [{"nome": c["nome"], "beta": c["beta"], "rotulo": c["rotulo"]}
                         for c in cfg["cenarios"]]}


def info_git():
    def roda(*args):
        try:
            r = subprocess.run(args, cwd=AQUI, capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""
    commit = roda("git", "rev-parse", "--short", "HEAD")
    if not commit:
        return {"commit": None, "limpo": None}
    return {"commit": commit, "limpo": roda("git", "status", "--porcelain") == ""}


def escreve_manifesto(pasta, fid, apelido, cfg, res, arquivos):
    man = {
        "fase": fid, "apelido": apelido,
        "descricao": cfg.get("descricao", ""),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "codigo": info_git(),
        "comum": assinatura(cfg)["comum"],
        "cenarios": [{
            "nome": r["nome"], "rotulo": r["rotulo"], "sufixo": sufixo(r), "beta": r["beta"],
            "arquivos": arquivos[r["nome"]],
            "resultado": {"sd_mediana": r["p50"], "sd_p90": r["p90"], "sd_p99": r["p99"],
                          "footprint_1000req": round(r["fp_1k"], 1) if r["fp_1k"] else None,
                          "objetos_distintos": r["distintos"],
                          "p_inf_medido": round(r["p_inf_medido"], 4),
                          "erro_max_hrc": round(r["erro_max"], 4), "confere": r["confere"]},
        } for r in res],
    }
    with open(os.path.join(pasta, "manifesto.json"), "w") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False)
    return man


def escreve_index():
    """Uma linha por fase, lida dos manifestos."""
    os.makedirs(FASES, exist_ok=True)
    linhas = []
    for d in lista_fases():
        cam = os.path.join(FASES, d, "manifesto.json")
        if not os.path.exists(cam):
            continue
        m = json.load(open(cam))
        c = m["comum"]
        betas = " / ".join(str(x["beta"]).replace(".", ",") for x in m["cenarios"])
        erro = max(x["resultado"]["erro_max_hrc"] for x in m["cenarios"])
        ok = all(x["resultado"]["confere"] for x in m["cenarios"])
        linhas.append("| [%s](%s/) | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            m["fase"], d, m["apelido"], m["gerado_em"][:10],
            format(c["dmax"], ",").replace(",", "."), str(c["inf"]).replace(".", ","),
            format(c["requisicoes"], ",").replace(",", "."), c["semente"],
            betas, str(round(erro, 4)).replace(".", ","), "sim" if ok else "**NAO**"))
    txt = ["# Fases de experimentacao", "",
           "Gerado por `pipeline.py`. Cada fase e uma rodada com parametros comuns proprios;",
           "os detalhes de cada uma estao no `manifesto.json` dentro da pasta.", "",
           "| Fase | Apelido | Data | dmax | inf | Requisicoes | Semente | Betas | Erro max | Confere |",
           "|---|---|---|---|---|---|---|---|---|---|"] + linhas + [""]
    with open(os.path.join(FASES, "INDEX.md"), "w") as fh:
        fh.write("\n".join(txt))


# --------------------------------------------------------------- etapa 1
def etapa_distribuicao(cfg, cen, caminho, fid):
    """Escreve a lista de stack distance do cenario e devolve (pmf, p_inf)."""
    args = SimpleNamespace(beta=cen["beta"], dmax=cfg["dmax"], inf=cfg["inf"])
    pmf, p_inf, cab = mkps.c_potencia(args)
    mkps.escreve(caminho, pmf, p_inf,
                 cab + ["fase: %s" % fid, "cenario: %s (%s)" % (cen["nome"], cen["rotulo"])])
    return pmf, p_inf


# --------------------------------------------------------------- etapa 2
def etapa_carga(cfg, cen, sd_path, caminho):
    """Gera o trace a partir da lista de SD. Devolve as linhas de aquecimento."""
    pmf, _ = genwl.load_sd_file(sd_path)
    prefixo = len(pmf)                              # --emit-warmup escreve uma linha por objeto
    args = SimpleNamespace(sd_file=sd_path, requests=cfg["requisicoes"], seed=cfg["semente"],
                           emit_warmup=True, sd_dist="zipf", sd_max=cfg["dmax"],
                           sd_beta=cen["beta"], sd_mu=6.0, sd_sigma=1.5, cold_prob=cfg["inf"])
    buf = []
    with open(caminho, "w") as fh:
        def out(o):
            buf.append(str(o))
            if len(buf) >= 65536:
                fh.write("\n".join(buf) + "\n"); buf.clear()
        with contextlib.redirect_stderr(io.StringIO()):   # o aviso do --emit-warmup nao interessa aqui
            genwl.gen_lrusm(args, out)
        if buf:
            fh.write("\n".join(buf) + "\n")
    return prefixo


# --------------------------------------------------------------- etapa 3
def grade_log(ate, n=44):
    """Pontos espacados por igual em escala log, de 1 ate 'ate'."""
    return sorted({max(1, int(round(10 ** (math.log10(ate) * i / (n - 1))))) for i in range(n)})


def teoria(pmf, p_inf):
    """hit(C) = (1 - P(inf)) * P(d < C)   e   cdf(x) = P(d < x | reuso).

    Em palavras: acerta quem e reuso (nao e objeto novo) e cuja stack distance cabe no cache."""
    n = len(pmf)
    acum = [0.0] * (n + 1)
    for d in range(n):
        acum[d + 1] = acum[d] + pmf[d]
    cdf = lambda x: acum[min(x, n)]
    hit = lambda C: (1 - p_inf) * cdf(C)
    return hit, cdf


def medir_footprint(ev, semente, dmax):
    """Footprint: quantos objetos distintos aparecem numa janela de n requisicoes.
    Media sobre janelas sorteadas ao acaso (semente fixa, entao e reprodutivel)."""
    rnd = random.Random(semente)
    n_tot = len(ev)
    janelas, j = [], 10
    while j <= min(n_tot // 2, 20 * dmax):
        janelas.append(j)
        j = j * 3 if str(j)[0] == "1" else int(round(j * 10 / 3))
    saida = []
    for j in janelas:
        amostras = max(30, min(150, 2000000 // j))
        tot = sum(len(set(ev[i:i + j])) for i in
                  (rnd.randrange(0, n_tot - j) for _ in range(amostras)))
        media = tot / amostras
        saida.append((j, media, media / j))
    return saida


def etapa_conferencia(cfg, cen, pmf, p_inf, carga_path, prefixo):
    trace = [l.strip() for l in open(carga_path) if l.strip()]
    sds = genwl.stack_distances(trace)[prefixo:]
    n = len(sds)
    fin = sorted(d for d in sds if d >= 0)
    r = len(fin)
    if r == 0:
        raise SystemExit("cenario %s: trace sem reusos" % cen["nome"])
    frios = n - r
    t_hit, t_cdf = teoria(pmf, p_inf)

    def m_hit(C):                                   # hit medido: reusos com d < C
        return bisect.bisect_left(fin, C) / n

    def m_cdf(x):                                   # fracao dos reusos com d < x
        return bisect.bisect_left(fin, x) / r

    pct = lambda q: fin[min(r - 1, int(q * (r - 1)))]
    grade = grade_log(cfg["dmax"])
    linhas_hrc = [(C, t_hit(C), m_hit(C)) for C in grade]
    linhas_cdf = [(x, t_cdf(x), m_cdf(x)) for x in grade]
    tabela = [(C, t_hit(C), m_hit(C), m_cdf(C)) for C in cfg["caches"]]
    erro = max(abs(t - m) for _, t, m, _ in tabela)

    # histograma de SD em faixas de uma oitava (x2)
    hist, lim = [], 1
    while lim <= cfg["dmax"]:
        prox = lim * 2
        c = bisect.bisect_left(fin, prox) - bisect.bisect_left(fin, lim)
        hist.append((lim, min(prox, cfg["dmax"]) - 1, c, c / r))
        lim = prox

    ev = trace[prefixo:]
    fp = medir_footprint(ev, cfg["semente"], cfg["dmax"])
    fp_1k = next((m for j, m, _ in fp if j == 1000), None)

    return {
        "nome": cen["nome"], "rotulo": cen["rotulo"], "beta": cen["beta"],
        "fp": fp, "fp_1k": fp_1k,
        "requisicoes": n, "prefixo": prefixo, "reusos": r,
        "p_inf_teorico": p_inf, "p_inf_medido": frios / n,
        "p25": pct(.25), "p50": pct(.50), "p75": pct(.75), "p90": pct(.90), "p99": pct(.99),
        "distintos": len(set(ev)),
        "hrc": linhas_hrc, "cdf": linhas_cdf, "tabela": tabela, "hist": hist,
        "erro_max": erro, "confere": erro <= cfg["tolerancia"],
    }


# --------------------------------------------------------------- saidas
def grava_csvs(cfg, res, analise, fid):
    escritos = []

    def w(nome, cab, linhas):
        arq = os.path.join(analise, "%s_%s.csv" % (nome, fid))
        with open(arq, "w", newline="") as fh:
            c = csv.writer(fh); c.writerow(cab); c.writerows(linhas)
        escritos.append(os.path.basename(arq))

    w("medidas",
      ["cenario", "rotulo", "beta", "dmax", "p_inf_alvo", "requisicoes", "aquecimento", "reusos",
       "p_inf_medido", "sd_p25", "sd_p50", "sd_p75", "sd_p90", "sd_p99", "objetos_distintos",
       "footprint_1000req", "erro_max_hrc", "confere"],
      [[r["nome"], r["rotulo"], r["beta"], cfg["dmax"], cfg["inf"], r["requisicoes"], r["prefixo"],
        r["reusos"], round(r["p_inf_medido"], 4), r["p25"], r["p50"], r["p75"], r["p90"], r["p99"],
        r["distintos"], round(r["fp_1k"], 1) if r["fp_1k"] else "", round(r["erro_max"], 4),
        "sim" if r["confere"] else "NAO"] for r in res])

    w("hrc", ["cenario", "cache_objetos", "hit_teorico", "hit_medido", "erro"],
      [[r["nome"], C, round(t, 5), round(m, 5), round(m - t, 5)] for r in res for C, t, m in r["hrc"]])

    w("sd_cdf", ["cenario", "d", "P(d<x)_teorico", "P(d<x)_medido"],
      [[r["nome"], x, round(t, 5), round(m, 5)] for r in res for x, t, m in r["cdf"]])

    w("sd_histograma", ["cenario", "faixa_de", "faixa_ate", "reusos", "fracao"],
      [[r["nome"], a, b, c, round(f, 5)] for r in res for a, b, c, f in r["hist"]])

    w("footprint", ["cenario", "janela_requisicoes", "objetos_distintos_media", "fracao_da_janela"],
      [[r["nome"], j, round(m, 1), round(f, 4)] for r in res for j, m, f in r["fp"]])

    w("conferencia", ["cenario", "cache_objetos", "hit_teorico", "hit_medido", "erro",
                      "fracao_reusos_que_cabem", "fracao_reusos_que_nao_cabem"],
      [[r["nome"], C, round(t, 5), round(m, 5), round(m - t, 5), round(f, 5), round(1 - f, 5)]
       for r in res for C, t, m, f in r["tabela"]])
    return escritos


# --------------------------------------------------------------- graficos
def svg_linhas(res, chave, titulo, ylab, xlab, xmax, w=640, h=330):
    """Uma linha por cenario (medido) com marcadores nos valores teoricos."""
    M = {"l": 62, "r": 18, "t": 16, "b": 46}
    lx = math.log10(xmax)
    sx = lambda g: M["l"] + (math.log10(max(g, 1)) / lx) * (w - M["l"] - M["r"])
    sy = lambda v: M["t"] + (1 - v) * (h - M["t"] - M["b"])
    p = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, titulo)]
    p.append('<style>.gx{stroke:var(--rule);stroke-width:1}.ax{stroke:var(--rule-strong);stroke-width:1}'
             '.tk{font:11px ui-monospace,monospace;fill:var(--muted)}'
             '.lb{font:12px system-ui,sans-serif;fill:var(--ink-2)}</style>')
    for v in (0, .25, .5, .75, 1):
        p.append('<line class="gx" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (M["l"], sy(v), w - M["r"], sy(v)))
        p.append('<text class="tk" x="%.1f" y="%.1f" text-anchor="end">%d%%</text>' % (M["l"] - 8, sy(v) + 4, v * 100))
    e = 1
    while e <= xmax:
        anc = "start" if e == 1 else ("end" if e * 10 > xmax else "middle")
        p.append('<text class="tk" x="%.1f" y="%.1f" text-anchor="%s">%s</text>'
                 % (sx(e), h - M["b"] + 18, anc, format(e, ",").replace(",", ".")))
        e *= 10
    p.append('<line class="ax" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (M["l"], sy(0), w - M["r"], sy(0)))
    p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (w / 2, h - 8, xlab))
    p.append('<text class="lb" transform="translate(14,%.1f) rotate(-90)" text-anchor="middle">%s</text>' % (h / 2, ylab))
    for i, r in enumerate(res):
        dados = r[chave]
        d = "".join(("L" if k else "M") + "%.1f,%.1f" % (sx(x), sy(m)) for k, (x, _, m) in enumerate(dados))
        p.append('<path d="%s" fill="none" stroke="var(--c%d)" stroke-width="2" stroke-linejoin="round"/>' % (d, i))
        for j, (x, t, _) in enumerate(dados):
            if j % 4 == 0:
                p.append('<circle cx="%.1f" cy="%.1f" r="3.4" fill="none" stroke="var(--c%d)" stroke-width="1.6"/>'
                         % (sx(x), sy(t), i))
    p.append("</svg>")
    return "\n".join(p)


def svg_loglog(res, chave, titulo, ylab, xlab, w=640, h=330):
    """Curva com os dois eixos em escala log (footprint x tamanho da janela)."""
    M = {"l": 62, "r": 18, "t": 16, "b": 46}
    xs = [ponto[0] for ponto in res[0][chave]]
    x0, x1 = min(xs), max(xs)
    ytopo = 10 ** math.ceil(math.log10(max(ponto[1] for r in res for ponto in r[chave])))
    lx, ly = math.log10(x1 / x0), math.log10(ytopo)
    sx = lambda g: M["l"] + (math.log10(g / x0) / lx) * (w - M["l"] - M["r"])
    sy = lambda v: M["t"] + (1 - math.log10(max(v, 1)) / ly) * (h - M["t"] - M["b"])
    fmt = lambda v: format(int(v), ",").replace(",", ".")
    p = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, titulo)]
    p.append('<style>.gx{stroke:var(--rule);stroke-width:1}.ax{stroke:var(--rule-strong);stroke-width:1}'
             '.tk{font:11px ui-monospace,monospace;fill:var(--muted)}'
             '.lb{font:12px system-ui,sans-serif;fill:var(--ink-2)}</style>')
    e = 1
    while e <= ytopo:
        p.append('<line class="gx" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (M["l"], sy(e), w - M["r"], sy(e)))
        p.append('<text class="tk" x="%.1f" y="%.1f" text-anchor="end">%s</text>' % (M["l"] - 8, sy(e) + 4, fmt(e)))
        e *= 10
    e = 10 ** math.ceil(math.log10(x0))
    while e <= x1:
        anc = "end" if e * 10 > x1 else "middle"
        p.append('<text class="tk" x="%.1f" y="%.1f" text-anchor="%s">%s</text>'
                 % (sx(e), h - M["b"] + 18, anc, fmt(e)))
        e *= 10
    p.append('<line class="ax" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (M["l"], sy(1), w - M["r"], sy(1)))
    p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (w / 2, h - 8, xlab))
    p.append('<text class="lb" transform="translate(14,%.1f) rotate(-90)" text-anchor="middle">%s</text>' % (h / 2, ylab))
    for i, r in enumerate(res):
        d = "".join(("L" if k else "M") + "%.1f,%.1f" % (sx(x), sy(m))
                    for k, (x, m, _) in enumerate(r[chave]))
        p.append('<path d="%s" fill="none" stroke="var(--c%d)" stroke-width="2" stroke-linejoin="round"/>' % (d, i))
        for x, m, _ in r[chave]:
            p.append('<circle cx="%.1f" cy="%.1f" r="3" fill="var(--c%d)"/>' % (sx(x), sy(m), i))
    p.append("</svg>")
    return "\n".join(p)


def svg_barras(res, w=640, h=330):
    """Histograma de SD: uma barra por faixa (x2), agrupada por cenario."""
    M = {"l": 62, "r": 18, "t": 16, "b": 46}
    faixas = [x[0] for x in res[0]["hist"]]
    topo = max(f for r in res for *_, f in r["hist"]) or 1
    topo = math.ceil(topo * 20) / 20
    larg = (w - M["l"] - M["r"]) / len(faixas)
    sy = lambda v: M["t"] + (1 - v / topo) * (h - M["t"] - M["b"])
    p = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" '
         'aria-label="Distribuicao da stack distance por faixa">' % (w, h)]
    p.append('<style>.gx{stroke:var(--rule);stroke-width:1}.ax{stroke:var(--rule-strong);stroke-width:1}'
             '.tk{font:11px ui-monospace,monospace;fill:var(--muted)}'
             '.lb{font:12px system-ui,sans-serif;fill:var(--ink-2)}</style>')
    passo = topo / 4
    for k in range(5):
        v = passo * k
        p.append('<line class="gx" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (M["l"], sy(v), w - M["r"], sy(v)))
        p.append('<text class="tk" x="%.1f" y="%.1f" text-anchor="end">%d%%</text>' % (M["l"] - 8, sy(v) + 4, round(v * 100)))
    bw = (larg - 6) / len(res)
    for j, ini in enumerate(faixas):
        x0 = M["l"] + j * larg + 3
        if j % 2 == 0:
            p.append('<text class="tk" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                     % (x0 + larg / 2 - 3, h - M["b"] + 18, format(ini, ",").replace(",", ".")))
        for i, r in enumerate(res):
            f = r["hist"][j][3]
            alt = max(0.0, sy(0) - sy(f))
            p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="var(--c%d)"/>'
                     % (x0 + i * bw, sy(f), max(bw - 2, 1), alt, i))
    p.append('<line class="ax" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (M["l"], sy(0), w - M["r"], sy(0)))
    p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="middle">stack distance (faixas dobrando)</text>' % (w / 2, h - 8))
    p.append('<text class="lb" transform="translate(14,%.1f) rotate(-90)" text-anchor="middle">%% dos reusos</text>' % (h / 2))
    p.append("</svg>")
    return "\n".join(p)


# --------------------------------------------------------------- relatorio
def n_br(v, casas=0):
    s = ("%.*f" % (casas, v)).replace(".", ",")
    inteiro, _, dec = s.partition(",")
    neg = inteiro.startswith("-")
    inteiro = inteiro.lstrip("-")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:]); inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return ("-" if neg else "") + ".".join(grupos) + ("," + dec if dec else "")


def grava_relatorio(cfg, res, svgs, analise, fid, apelido):
    linhas_res, linhas_conf = [], []
    for i, r in enumerate(res):
        linhas_res.append(
            "<tr><td><span class='pt' style='background:var(--c%d)'></span>%s</td><td class='n'>%s</td>"
            "<td class='n'>%s</td><td class='n'>%s</td><td class='n'>%s</td><td class='n'>%s</td>"
            "<td class='n'>%s</td><td class='n'>%s</td><td class='%s'>%s</td></tr>"
            % (i, r["rotulo"], n_br(r["beta"], 1), n_br(r["p50"]), n_br(r["p90"]),
               n_br(r["p99"]), n_br(r["fp_1k"]) if r["fp_1k"] else "-",
               n_br(r["p_inf_medido"] * 100, 1) + "%", n_br(r["distintos"]),
               "ok" if r["confere"] else "ruim",
               ("confere (erro %s)" % n_br(r["erro_max"], 4)) if r["confere"]
               else ("NAO confere (erro %s)" % n_br(r["erro_max"], 4))))
        for C, t, m, f in r["tabela"]:
            linhas_conf.append(
                "<tr><td>%s</td><td class='n'>%s</td><td class='n'>%s</td><td class='n'>%s</td>"
                "<td class='n'>%s</td><td class='n'>%s</td></tr>"
                % (r["rotulo"], n_br(C), n_br(t, 4), n_br(m, 4), n_br(m - t, 4), n_br(f * 100, 1) + "%"))
    legenda = " ".join("<span class='leg'><i style='background:var(--c%d)'></i>%s (β = %s)</span>"
                       % (i, r["rotulo"], n_br(r["beta"], 1)) for i, r in enumerate(res))
    cores_claro = "".join("--c%d:%s;" % (i, CORES[i % 3]) for i in range(len(res)))
    cores_escuro = "".join("--c%d:%s;" % (i, CORES_ESC[i % 3]) for i in range(len(res)))
    ctx = dict(data=datetime.now().strftime("%d/%m/%Y %H:%M"), legenda=legenda,
               fase=fid, apelido=apelido, descricao=cfg.get("descricao", ""),
               cores_claro=cores_claro, cores_escuro=cores_escuro,
               dmax=n_br(cfg["dmax"]), inf=n_br(cfg["inf"] * 100, 1), req=n_br(cfg["requisicoes"]),
               semente=cfg["semente"], tol=n_br(cfg["tolerancia"], 3),
               linhas_res="\n".join(linhas_res), linhas_conf="\n".join(linhas_conf), **svgs)
    with open(os.path.join(AQUI, "modelo_relatorio.html")) as fh:
        modelo = fh.read()
    for chave, valor in ctx.items():
        modelo = modelo.replace("{{%s}}" % chave, str(valor))
    saida = os.path.join(analise, "relatorio_%s.html" % fid)
    with open(saida, "w") as fh:
        fh.write(modelo)
    return saida


# --------------------------------------------------------------- main
def roda_fase(pasta, so_analise, refazer):
    fid, apelido = id_da_pasta(os.path.basename(pasta)), os.path.basename(pasta).split("-", 1)[-1]
    cfg = json.load(open(os.path.join(pasta, "cenarios.json")))
    dist, cargas, analise = (os.path.join(pasta, d) for d in ("dist", "cargas", "analise"))
    for d in (dist, cargas, analise):
        os.makedirs(d, exist_ok=True)

    man_path = os.path.join(pasta, "manifesto.json")
    if os.path.exists(man_path) and not refazer and not so_analise:
        antigo = json.load(open(man_path))
        atual = assinatura(cfg)
        if antigo.get("comum") != atual["comum"] or \
           [{k: c[k] for k in ("nome", "beta", "rotulo")} for c in antigo.get("cenarios", [])] != atual["cenarios"]:
            raise SystemExit(
                "o cenarios.json da fase %s mudou desde a ultima rodada.\n"
                "Rode com --refazer para sobrescrever esta fase, ou crie outra com --nova-fase." % fid)

    print("== fase %s (%s) -- %s" % (fid, apelido, cfg.get("descricao", "sem descricao")))
    res, arquivos = [], {}
    for cen in cfg["cenarios"]:
        suf = sufixo(cen)
        sd_path = os.path.join(dist, "sd_%s_%s.txt" % (fid, suf))
        carga_path = os.path.join(cargas, "carga_%s_%s.txt" % (fid, suf))
        print("   cenario %s (beta = %s)" % (suf, cen["beta"]))
        if so_analise:
            pmf, p_inf = genwl.load_sd_file(sd_path)
            prefixo = len(pmf)
        else:
            pmf, p_inf = etapa_distribuicao(cfg, cen, sd_path, fid)
            print("      1. distribuicao ->", os.path.relpath(sd_path, pasta))
            prefixo = etapa_carga(cfg, cen, sd_path, carga_path)
            print("      2. carga        ->", os.path.relpath(carga_path, pasta))
        r = etapa_conferencia(cfg, cen, pmf, p_inf, carga_path, prefixo)
        print("      3. conferencia  -> mediana da SD %d | footprint em 1.000 req %s | "
              "erro max na HRC %.4f | %s"
              % (r["p50"], ("%.0f" % r["fp_1k"]) if r["fp_1k"] else "-", r["erro_max"],
                 "confere" if r["confere"] else "NAO CONFERE"))
        res.append(r)
        arquivos[cen["nome"]] = {"dist": os.path.relpath(sd_path, pasta),
                                 "carga": os.path.relpath(carga_path, pasta)}

    grava_csvs(cfg, res, analise, fid)
    svgs = {"svg_hrc": svg_linhas(res, "hrc", "Curva de hit rate", "hit rate",
                                  "tamanho do cache (objetos)", cfg["dmax"]),
            "svg_cdf": svg_linhas(res, "cdf", "Acumulada da stack distance",
                                  "% dos reúsos com SD menor que x", "stack distance x", cfg["dmax"]),
            "svg_fp": svg_loglog(res, "fp", "Footprint", "objetos distintos",
                                 "tamanho da janela (requisições)"),
            "svg_hist": svg_barras(res)}
    for nome, conteudo in (("hrc", svgs["svg_hrc"]), ("sd_cdf", svgs["svg_cdf"]),
                           ("footprint", svgs["svg_fp"]), ("sd_histograma", svgs["svg_hist"])):
        with open(os.path.join(analise, "%s_%s.svg" % (nome, fid)), "w") as fh:
            fh.write(conteudo.replace("var(--rule-strong)", "#B4C3C1").replace("var(--rule)", "#D3DDDB")
                     .replace("var(--muted)", "#5E7174").replace("var(--ink-2)", "#3A4A4C")
                     .replace("var(--c0)", CORES[0]).replace("var(--c1)", CORES[1]).replace("var(--c2)", CORES[2]))
    rel = grava_relatorio(cfg, res, svgs, analise, fid, apelido)
    escreve_manifesto(pasta, fid, apelido, cfg, res, arquivos)
    escreve_index()
    print("\nanalise em %s | relatorio: %s" % (os.path.relpath(analise, AQUI),
                                               os.path.relpath(rel, AQUI)))
    print("indice das fases:", os.path.relpath(os.path.join(FASES, "INDEX.md"), AQUI))
    if not all(r["confere"] for r in res):
        sys.exit("ALGUM CENARIO NAO CONFERE - veja analise/conferencia_%s.csv" % fid)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fase", help="id (f02) ou nome da pasta da fase a rodar")
    ap.add_argument("--nova-fase", metavar="APELIDO",
                    help="cria uma fase nova a partir de cenarios.json e para, para voce editar")
    ap.add_argument("--fases", action="store_true", help="lista as fases ja rodadas")
    ap.add_argument("--so-analise", action="store_true", help="nao regera distribuicoes nem cargas")
    ap.add_argument("--refazer", action="store_true",
                    help="sobrescreve a fase mesmo que a configuracao tenha mudado")
    a = ap.parse_args()

    if a.nova_fase:
        nova_fase(a.nova_fase)
        return
    if a.fases:
        escreve_index()
        caminho = os.path.join(FASES, "INDEX.md")
        print(open(caminho).read() if os.path.exists(caminho) else "nenhuma fase ainda")
        return
    if not a.fase:
        fases = lista_fases()
        raise SystemExit("informe a fase: --fase <id>. Fases: %s"
                         % (", ".join(fases) if fases else "nenhuma; crie com --nova-fase <apelido>"))
    roda_fase(acha_fase(a.fase), a.so_analise, a.refazer)


if __name__ == "__main__":
    main()
