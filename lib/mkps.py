#!/usr/bin/env python3
"""
mkps.py - constroi a distribuicao de stack distance P(s) que o genwl.py consome.

E um passo SEPARADO da geracao:

    mkps.py  ->  ps.txt  ->  genwl.py gen --sd-file ps.txt  ->  trace  ->  genwl.py analyze

Aqui "d" e a stack distance em NUMERO DE OBJETOS DISTINTOS pedidos entre dois
pedidos ao mesmo objeto (d = 0 e um re-pedido imediato). Num cache LRU de C
objetos, a requisicao acerta se d < C, logo

    miss(C) = P(inf) + P(d >= C)

que o comando imprime junto com o arquivo - e o gabarito analitico do trace.

Construtores:
  faixas       porcentagem dos reusos em cada faixa de SD (o mais simples)
  potencia     lei de potencia na propria distancia: P(d) ~ (d+1)^-beta
  irm          popularidade Zipf(alpha) sobre N objetos, convertida em P(d)
  mistura      soma ponderada de componentes (hot set, loop, working set, cauda)
  mrc          voce da pontos da curva de miss desejada; o resto e deduzido
  trace        mede a P(d) de um trace existente
  transformar  estica, recombina ou troca o P(inf) de arquivos ja prontos
"""
import argparse, math, os, sys

try:
    import numpy as np
except ImportError:
    np = None


# --------------------------------------------------------------- utilidades
def normaliza(w):
    t = sum(w)
    if t <= 0:
        raise SystemExit("distribuicao vazia: todos os pesos deram zero")
    return [x / t for x in w]


def escreve(path, pmf, p_inf, cabecalho):
    """Escreve no formato do genwl, agrupando faixas de probabilidade igual."""
    out = sys.stdout if path == "-" else open(path, "w")
    for l in cabecalho:
        out.write("# " + l + "\n")
    out.write("# d = objetos distintos entre dois pedidos ao mesmo objeto\n")
    pmf = [x * (1.0 - p_inf) for x in pmf]   # o arquivo soma 1 contando o 'inf'
    i, n = 0, len(pmf)
    while i < n:
        j = i
        while j + 1 < n and abs(pmf[j + 1] - pmf[i]) <= 1e-15:
            j += 1
        p = pmf[i] * (j - i + 1)
        if p > 0:
            out.write(("%d %.10g\n" % (i, p)) if i == j else ("%d-%d %.10g\n" % (i, j, p)))
        i = j + 1
    if p_inf > 0:
        out.write("inf %.10g\n" % p_inf)
    if out is not sys.stdout:
        out.close()


def resumo(pmf, p_inf, dmax_print=None):
    """miss(C) = P(inf) + P(d >= C). Impresso no stderr para nao sujar o arquivo."""
    n = len(pmf)
    cauda = [0.0] * (n + 1)
    for d in range(n - 1, -1, -1):
        cauda[d] = cauda[d + 1] + pmf[d]
    media = sum(d * p for d, p in enumerate(pmf))
    acc, mediana = 0.0, n - 1
    for d, p in enumerate(pmf):
        acc += p
        if acc >= 0.5:
            mediana = d
            break
    e = sys.stderr
    print("P(inf) = %.4f   |   d finita: media %.1f, mediana %d, maximo %d"
          % (p_inf, media, mediana, n - 1), file=e)
    print("MRC teorica de LRU (miss ratio):", file=e)
    print("  %12s  %9s" % ("cache(objs)", "miss"), file=e)
    for c in sorted(set([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000,
                         10000, 20000, 50000, 100000])):
        if c > n:
            break
        print("  %12d  %9.4f" % (c, p_inf + (1 - p_inf) * cauda[c]), file=e)


# ------------------------------------------------------------- construtores
def c_faixas(a):
    """Divide a SD em faixas e diz que porcentagem dos reusos cai em cada uma.
    Dentro de uma faixa, todo valor tem a mesma chance."""
    lim = [int(x) for x in a.limites.split(",")]
    pes = [float(x) for x in a.pesos.split(",")]
    if len(pes) != len(lim) - 1:
        raise SystemExit("--pesos precisa de %d valores (um por faixa); recebeu %d" % (len(lim) - 1, len(pes)))
    if any(lim[i + 1] <= lim[i] for i in range(len(lim) - 1)):
        raise SystemExit("--limites precisa ser crescente, ex.: 0,100,1000,10000")
    tot = sum(pes)
    w = [0.0] * lim[-1]
    cab = ["faixas: limites=%s pesos=%s inf=%g" % (a.limites, a.pesos, a.inf)]
    for i, p in enumerate(pes):
        lo, hi = lim[i], lim[i + 1]
        for d in range(lo, hi):
            w[d] += (p / tot) / (hi - lo)
        linha = "faixa %d: SD de %d a %d -> %.1f%% dos reusos" % (i + 1, lo, hi - 1, 100 * p / tot)
        cab.append(linha)
        print(linha, file=sys.stderr)
    return normaliza(w), a.inf, cab


def c_potencia(a):
    w = [(d + 1.0) ** (-a.beta) for d in range(a.dmax)]
    return normaliza(w), a.inf, ["potencia: beta=%g dmax=%d inf=%g" % (a.beta, a.dmax, a.inf)]


def c_irm(a):
    """Zipf(alpha) sobre N objetos -> P(d), pela aproximacao de Che.

    Para um 'tempo caracteristico' T, um objeto de popularidade p esta no cache
    com probabilidade 1 - e^(-p T). Somando sobre os objetos sai o tamanho C(T)
    do cache, e ponderando por p sai a hit rate h(T). Variando T tem-se a curva
    inteira; P(d = k) = h(k+1) - h(k)."""
    N = a.objetos
    if np is not None:
        p = np.arange(1, N + 1, dtype=float) ** (-a.alpha)
        p /= p.sum()
        T = np.exp(np.linspace(math.log(1e-4), math.log(1e7), 4000))
        x = np.clip(np.outer(T, p), 0, 700)
        pres = 1.0 - np.exp(-x)
        C = pres.sum(axis=1)
        h = (pres * p).sum(axis=1)
        alvo = np.arange(1, N + 1, dtype=float)
        hC = np.interp(alvo, C, h)
    else:
        p = normaliza([(i + 1.0) ** (-a.alpha) for i in range(N)])
        C, h = [], []
        for k in range(4000):
            T = math.exp(math.log(1e-4) + (math.log(1e7) - math.log(1e-4)) * k / 3999)
            c = s = 0.0
            for pi in p:
                q = 1.0 - math.exp(-min(pi * T, 700))
                c += q
                s += q * pi
            C.append(c); h.append(s)
        hC = []
        for c in range(1, N + 1):
            j = min(range(len(C)), key=lambda i: abs(C[i] - c))
            hC.append(h[j])
    pmf, ant = [], 0.0
    for k in range(N):
        v = max(0.0, float(hC[k]) - ant)
        pmf.append(v)
        ant = float(hC[k])
    return normaliza(pmf), a.inf, [
        "irm: alpha=%g objetos=%d inf=%g" % (a.alpha, N, a.inf),
        "P(d) derivada de uma popularidade Zipf pela aproximacao de Che"]


def _componente(spec, dmax):
    partes = spec.split(":")
    peso, tipo, args = float(partes[0]), partes[1], [float(x) for x in partes[2:]]
    w = [0.0] * dmax
    if tipo == "exp":                      # hot set: media m
        m = args[0]
        for d in range(dmax):
            w[d] = math.exp(-d / m)
    elif tipo == "lognormal":              # working set em torno de uma mediana
        med, sig = args[0], args[1]
        lm = math.log(med + 1.0)
        for d in range(dmax):
            x = math.log(d + 1.0)
            w[d] = math.exp(-((x - lm) ** 2) / (2 * sig * sig)) / (d + 1.0)
    elif tipo == "loop":                   # varredura ciclica de L objetos
        L = int(args[0]); jit = int(args[1]) if len(args) > 1 else 0
        a0, b0 = max(0, L - 1 - jit), min(dmax - 1, L - 1 + jit)
        for d in range(a0, b0 + 1):
            w[d] = 1.0
    elif tipo == "uniforme":
        a0, b0 = int(args[0]), min(int(args[1]), dmax - 1)
        for d in range(a0, b0 + 1):
            w[d] = 1.0
    elif tipo == "potencia":
        for d in range(dmax):
            w[d] = (d + 1.0) ** (-args[0])
    else:
        raise SystemExit("componente desconhecido: " + tipo)
    w = normaliza(w)
    return [peso * x for x in w]


def c_mistura(a):
    acc = [0.0] * a.dmax
    for spec in a.comp:
        for d, v in enumerate(_componente(spec, a.dmax)):
            acc[d] += v
    return normaliza(acc), a.inf, ["mistura: " + " + ".join(a.comp), "dmax=%d inf=%g" % (a.dmax, a.inf)]


def c_mrc(a):
    pts = []
    for par in a.pontos.split(","):
        c, m = par.split(":")
        pts.append((int(c), float(m)))
    pts.sort()
    for i in range(1, len(pts)):
        if pts[i][1] > pts[i - 1][1] + 1e-12:
            raise SystemExit("a curva de miss nao pode subir: %s depois de %s" % (pts[i], pts[i - 1]))
    p_inf = a.inf if a.inf is not None else pts[-1][1]
    if p_inf > pts[-1][1] + 1e-12:
        raise SystemExit("inf=%g nao pode passar do miss do ultimo ponto (%g)" % (p_inf, pts[-1][1]))
    dmax = a.dmax or pts[-1][0]
    faixas = []                                   # (a, b, massa) com d em [a, b)
    faixas.append((0, pts[0][0], 1.0 - pts[0][1]))
    for i in range(len(pts) - 1):
        faixas.append((pts[i][0], pts[i + 1][0], pts[i][1] - pts[i + 1][1]))
    if pts[-1][1] - p_inf > 1e-12:
        if dmax <= pts[-1][0]:
            raise SystemExit("use --dmax maior que %d para acomodar a massa entre o ultimo ponto e inf"
                             % pts[-1][0])
        faixas.append((pts[-1][0], dmax, pts[-1][1] - p_inf))
    n = max(b for _, b, _ in faixas)
    w = [0.0] * n
    for a0, b0, massa in faixas:
        if massa <= 0 or b0 <= a0:
            continue
        peso = [1.0 / (d + 1.0) if a.interp == "log" else 1.0 for d in range(a0, b0)]
        tot = sum(peso)
        for k, d in enumerate(range(a0, b0)):
            w[d] += massa * peso[k] / tot
    total = sum(w)
    return [x / total for x in w], p_inf, [
        "mrc: pontos=%s inf=%g interp=%s" % (a.pontos, p_inf, a.interp),
        "P(d) deduzida de miss(C) = P(inf) + P(d >= C)"]


def c_trace(a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import genwl
    tr = [l.strip() for l in open(a.entrada) if l.strip()]
    sds = genwl.stack_distances(tr)[a.skip:]
    fin = [d for d in sds if d >= 0]
    if not fin:
        raise SystemExit("trace sem reusos")
    n = len(sds)
    p_inf = (n - len(fin)) / n
    w = [0.0] * (max(fin) + 1)
    for d in fin:
        w[d] += 1.0
    return normaliza(w), p_inf, ["trace: %s (%d requisicoes, %d ignoradas)" % (a.entrada, n, a.skip)]


def c_transformar(a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import genwl
    acc, p_inf, nomes = None, 0.0, []
    pesos = []
    for spec in a.entrada:
        caminho, _, peso = spec.partition(":")
        pesos.append(float(peso) if peso else 1.0)
        nomes.append(spec)
    pesos = normaliza(pesos)
    for (spec, peso) in zip(a.entrada, pesos):
        caminho = spec.partition(":")[0]
        pmf, pi = genwl.load_sd_file(caminho)
        if a.esticar != 1.0:                       # d -> round(k*d)
            novo = [0.0] * (int(round((len(pmf) - 1) * a.esticar)) + 1)
            for d, p in enumerate(pmf):
                novo[int(round(d * a.esticar))] += p
            pmf = novo
        if acc is None or len(pmf) > len(acc):
            acc = (acc or []) + [0.0] * (len(pmf) - len(acc or []))
        for d, p in enumerate(pmf):
            acc[d] += peso * p
        p_inf += peso * pi
    if a.inf is not None:
        p_inf = a.inf
    return normaliza(acc), p_inf, ["transformar: %s esticar=%g inf=%g" % (",".join(nomes), a.esticar, p_inf)]


# --------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("-o", "--out", default="-", help="arquivo de saida (padrao: stdout)")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("faixas", parents=[comum], help="porcentagem dos reusos em cada faixa de SD")
    q.add_argument("--limites", default="0,100,1000,10000",
                   help="bordas das faixas; 0,100,1000,10000 = [0-99] [100-999] [1000-9999]")
    q.add_argument("--pesos", required=True, help="porcentagem dos reusos em cada faixa, ex.: 80,15,5")
    q.add_argument("--inf", type=float, default=0.05, help="fracao das requisicoes que sao objetos novos")
    q.set_defaults(f=c_faixas)

    q = sub.add_parser("potencia", parents=[comum], help="P(d) ~ (d+1)^-beta")
    q.add_argument("--beta", type=float, default=0.9)
    q.add_argument("--dmax", type=int, default=10000)
    q.add_argument("--inf", type=float, default=0.05)
    q.set_defaults(f=c_potencia)

    q = sub.add_parser("irm", parents=[comum], help="popularidade Zipf -> P(d)")
    q.add_argument("--alpha", type=float, default=0.9)
    q.add_argument("--objetos", type=int, default=10000)
    q.add_argument("--inf", type=float, default=0.0)
    q.set_defaults(f=c_irm)

    q = sub.add_parser("mistura", parents=[comum], help="soma ponderada de componentes")
    q.add_argument("--comp", action="append", required=True,
                   metavar="PESO:TIPO:PARAMS",
                   help="exp:m | lognormal:mediana:sigma | loop:L[:jitter] | uniforme:a:b | potencia:beta")
    q.add_argument("--dmax", type=int, default=10000)
    q.add_argument("--inf", type=float, default=0.05)
    q.set_defaults(f=c_mistura)

    q = sub.add_parser("mrc", parents=[comum], help="pontos da curva de miss desejada -> P(d)")
    q.add_argument("--pontos", required=True, metavar="C:miss,C:miss,...")
    q.add_argument("--inf", type=float, default=None)
    q.add_argument("--dmax", type=int, default=None)
    q.add_argument("--interp", choices=["log", "linear"], default="log")
    q.set_defaults(f=c_mrc)

    q = sub.add_parser("trace", parents=[comum], help="mede a P(d) de um trace")
    q.add_argument("entrada")
    q.add_argument("--skip", type=int, default=0)
    q.set_defaults(f=c_trace)

    q = sub.add_parser("transformar", parents=[comum], help="estica / recombina arquivos prontos")
    q.add_argument("entrada", nargs="+", metavar="ARQUIVO[:PESO]")
    q.add_argument("--esticar", type=float, default=1.0, help="multiplica todas as distancias")
    q.add_argument("--inf", type=float, default=None)
    q.set_defaults(f=c_transformar)

    a = p.parse_args()
    pmf, p_inf, cab = a.f(a)
    escreve(a.out, pmf, p_inf, cab)
    resumo(pmf, p_inf)
    if a.out != "-":
        print("escrito: %s" % a.out, file=sys.stderr)


if __name__ == "__main__":
    main()
