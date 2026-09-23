#!/usr/bin/env python3
"""
genwl.py - gerador e analisador de cargas sinteticas de cache com
stack-distance (reuse distance em objetos unicos) controlada.

Geradores
  irm    Independent Reference Model: popularidade Zipf(alpha) sobre N objetos.
         Voce controla a POPULARIDADE; a stack-distance emerge.
  lrusm  LRU Stack Model (Mattson'70; Turner & Strecker, CACM 1977):
         a cada passo amostra-se a profundidade d na pilha LRU de uma
         distribuicao alvo P(d) e o objeto naquela profundidade e referenciado.
         Voce controla a STACK-DISTANCE (== IRR do LIRS); a popularidade emerge.
         Este e o mesmo principio usado por TRAGEN/JEDI (com pesos em bytes).

Analise
  --analyze  histograma de stack-distance + MRC exata de LRU (Mattson) + FIFO
  --shards R amostragem espacial hash-based (SHARDS) antes da analise, para
             estudar o vies de amostragem sobre SD/MRC.

Uso rapido:
  # P(s) escrita por voce, num arquivo (ver formato em load_sd_file)
  python3 genwl.py gen  --model lrusm --sd-file minha_ps.txt \
                        --emit-warmup --requests 200000 -o trace.txt
  python3 genwl.py analyze trace.txt --skip <linhas de aquecimento> --sizes 1,10,100,1000
  # P(s) de uma familia parametrica
  python3 genwl.py gen  --model lrusm --sd-dist zipf --sd-beta 0.8 \
                        --cold-prob 0.02 --requests 200000 -o trace.txt
  python3 genwl.py gen  --model irm --objects 20000 --alpha 1.0 \
                        --requests 200000 -o trace_irm.txt
  python3 genwl.py analyze trace.txt --mrc-points 12
  python3 genwl.py analyze trace.txt --mrc-points 12 --shards 0.01
"""
import argparse, hashlib, math, random, sys
from collections import Counter


# --------------------------------------------------------------------------
# Lista com estatistica de ordem (Fenwick sobre slots) -> move-to-front O(log n)
# --------------------------------------------------------------------------
class OrderStat:
    """Pilha LRU: posicao 0 = topo (MRU). Suporta at(d), move_to_front, push_front."""

    def __init__(self, capacity):
        self.cap = capacity + 2
        self.tree = [0] * (self.cap + 1)     # Fenwick de ocupacao
        self.slot = [None] * (self.cap + 1)  # slot -> obj
        self.pos = {}                        # obj -> slot
        self.head = self.cap                 # proximo slot livre (cresce p/ esquerda)
        self.n = 0
        self.logn = self.cap.bit_length()

    def _add(self, i, v):
        while i <= self.cap:
            self.tree[i] += v
            i += i & -i

    def _kth(self, k):
        """menor slot i com prefix_sum(i) == k (k >= 1)"""
        i, rem = 0, k
        for j in range(self.logn, -1, -1):
            nxt = i + (1 << j)
            if nxt <= self.cap and self.tree[nxt] < rem:
                i = nxt
                rem -= self.tree[i]
        return i + 1

    def at(self, d):
        return self.slot[self._kth(d + 1)]

    def _alloc_front(self, obj):
        self.head -= 1
        if self.head < 1:                       # compacta se acabou o espaco
            self._compact()
            self.head -= 1
        s = self.head
        self.slot[s] = obj
        self.pos[obj] = s
        self._add(s, 1)
        self.n += 1

    def _compact(self):
        items = [self.slot[self._kth(k)] for k in range(1, self.n + 1)]
        self.tree = [0] * (self.cap + 1)
        self.slot = [None] * (self.cap + 1)
        self.pos = {}
        self.head = self.cap
        self.n = 0
        for obj in reversed(items):             # reinsere do LRU para o MRU
            self._alloc_front(obj)

    def remove_at(self, d):
        s = self._kth(d + 1)
        obj = self.slot[s]
        self.slot[s] = None
        del self.pos[obj]
        self._add(s, -1)
        self.n -= 1
        return obj

    def remove_obj(self, obj):
        s = self.pos.pop(obj)
        self.slot[s] = None
        self._add(s, -1)
        self.n -= 1

    def rank(self, obj):
        """stack distance atual do objeto (0 = MRU); None se ausente"""
        s = self.pos.get(obj)
        if s is None:
            return None
        r, i = 0, s
        while i > 0:
            r += self.tree[i]
            i -= i & -i
        return r - 1

    def push_front(self, obj):
        self._alloc_front(obj)

    def move_to_front_at(self, d):
        obj = self.remove_at(d)
        self._alloc_front(obj)
        return obj

    def move_to_front_obj(self, obj):
        self.remove_obj(obj)
        self._alloc_front(obj)


# --------------------------------------------------------------------------
# Distribuicoes de stack distance
# --------------------------------------------------------------------------
def sd_pmf(kind, dmax, beta, mu, sigma):
    """PMF sobre d = 0..dmax-1 (nao inclui o 'infinito'/cold miss)."""
    if kind == "zipf":                # P(d) ~ (d+1)^-beta  (cauda pesada)
        w = [(d + 1.0) ** (-beta) for d in range(dmax)]
    elif kind == "lognormal":         # corpo unimodal em escala log
        w = []
        for d in range(dmax):
            x = math.log(d + 1.0)
            w.append(math.exp(-((x - mu) ** 2) / (2 * sigma * sigma)) / (d + 1.0))
    elif kind == "uniform":
        w = [1.0] * dmax
    elif kind == "exp":               # localidade forte, cauda leve
        w = [math.exp(-(d + 1.0) / max(beta, 1e-9)) for d in range(dmax)]
    else:
        raise SystemExit("sd-dist desconhecida: " + kind)
    s = sum(w)
    return [x / s for x in w]


def build_cdf(pmf):
    cdf, acc = [], 0.0
    for p in pmf:
        acc += p
        cdf.append(acc)
    return cdf


def sample_cdf(cdf, u):
    lo, hi = 0, len(cdf) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if u <= cdf[mid]:
            hi = mid
        else:
            lo = mid + 1
    return lo


def load_sd_file(path):
    """P(s) definida pelo usuario. Uma entrada por linha, '#' comenta:
         d     prob    stack distance exata d (objetos distintos entre os pedidos)
         a-b   prob    prob espalhada por igual entre d = a .. b
         inf   prob    objeto novo (primeira referencia)
       As probabilidades sao normalizadas; nao precisam somar 1."""
    fin, cold = {}, 0.0
    for num, ln in enumerate(open(path), 1):
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        try:
            key, p = ln.split()[:2]
            p = float(p)
            if key.lower() in ("inf", "\u221e"):
                cold += p
            elif "-" in key:
                a, b = (int(x) for x in key.split("-"))
                for d in range(a, b + 1):
                    fin[d] = fin.get(d, 0.0) + p / (b - a + 1)
            else:
                fin[int(key)] = fin.get(int(key), 0.0) + p
        except ValueError:
            raise SystemExit("%s, linha %d: esperado 'd prob', 'a-b prob' ou 'inf prob'" % (path, num))
    if not fin or sum(fin.values()) <= 0:
        raise SystemExit("%s: e preciso ao menos uma stack distance finita com prob > 0" % path)
    tot = sum(fin.values()) + cold
    dmax = max(fin) + 1
    finite = tot - cold
    return [fin.get(d, 0.0) / finite for d in range(dmax)], cold / tot


# --------------------------------------------------------------------------
# Geradores
# --------------------------------------------------------------------------
def gen_lrusm(args, out):
    rnd = random.Random(args.seed)
    if args.sd_file:
        pmf, cold = load_sd_file(args.sd_file)
    else:
        pmf = sd_pmf(args.sd_dist, args.sd_max, args.sd_beta, args.sd_mu, args.sd_sigma)
        cold = args.cold_prob
    dmax = len(pmf)
    cdf = build_cdf(pmf)
    stack = OrderStat(args.requests + dmax + 8)
    for k in range(dmax - 1, -1, -1):        # pilha inicial: objetos 0..dmax-1, o 0 no topo
        stack.push_front(k)
    if args.emit_warmup:                     # prefixo que deixa um LRU exatamente nesse estado
        for k in range(dmax - 1, -1, -1):
            out(k)
        print("prefixo de aquecimento: %d linhas -> use --skip %d no analyze "
              "(ou descarte-as das estatisticas do seu simulador)" % (dmax, dmax), file=sys.stderr)
    nxt_id = dmax
    for _ in range(args.requests):
        if rnd.random() < cold:              # stack distance = infinito -> objeto novo
            obj = nxt_id
            nxt_id += 1
            stack.push_front(obj)
        else:
            d = sample_cdf(cdf, rnd.random())
            obj = stack.move_to_front_at(min(d, stack.n - 1))
        out(obj)


def gen_irm(args, out):
    rnd = random.Random(args.seed)
    n, a = args.objects, args.alpha
    w = [(i + 1.0) ** (-a) for i in range(n)]
    cdf = build_cdf([x / sum(w) for x in w])
    for _ in range(args.requests):
        out(sample_cdf(cdf, rnd.random()))


# --------------------------------------------------------------------------
# Analise: stack distance (Mattson) + MRC LRU + MRC FIFO
# --------------------------------------------------------------------------
def stack_distances(trace):
    st = OrderStat(len(trace) + 8)
    sds = []
    for obj in trace:
        r = st.rank(obj)
        if r is None:
            sds.append(-1)                  # cold miss (SD infinita)
            st.push_front(obj)
        else:
            sds.append(r)
            st.move_to_front_obj(obj)
    return sds


def mrc_lru_from_sd(sds, sizes):
    m = len(sds)
    return [sum(1 for d in sds if d < 0 or d >= c) / m for c in sizes]


def mrc_fifo(trace, sizes, skip=0):
    from collections import deque
    out = []
    for c in sizes:
        q, s, miss = deque(), set(), 0
        for i, obj in enumerate(trace):
            if obj in s:
                continue
            if i >= skip:
                miss += 1
            if len(q) >= c:
                s.discard(q.popleft())
            q.append(obj)
            s.add(obj)
        out.append(miss / (len(trace) - skip))
    return out


def shards_filter(trace, rate, modulus=(1 << 24)):
    t = int(rate * modulus)
    keep, idx = [], []
    for i, obj in enumerate(trace):
        h = int(hashlib.blake2b(repr(obj).encode(), digest_size=8).hexdigest(), 16)
        if h % modulus < t:
            keep.append(obj)
            idx.append(i)
    return keep, idx


def hist_lines(sds, nbins=12):
    fin = [d for d in sds if d >= 0]
    cold = len(sds) - len(fin)
    lines = ["  SD=inf (cold/1st ref) : %7d  (%5.2f%%)" % (cold, 100 * cold / len(sds))]
    if not fin:
        return lines
    mx = max(fin)
    edges = [0] + [int(2 ** (math.log2(max(mx, 1)) * (i + 1) / nbins)) for i in range(nbins)]
    c = Counter()
    for d in fin:
        for i in range(nbins):
            if d <= edges[i + 1]:
                c[i] += 1
                break
    for i in range(nbins):
        if c[i]:
            lines.append("  SD %s%7d, %7d] : %7d  (%5.2f%%)"
                         % ("[" if i == 0 else "(", edges[i], edges[i + 1], c[i], 100 * c[i] / len(sds)))
    return lines


# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="gera trace sintetico")
    g.add_argument("--model", choices=["lrusm", "irm"], default="lrusm")
    g.add_argument("--requests", type=int, default=200000)
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("-o", "--out", default="-")
    # lrusm
    g.add_argument("--sd-dist", choices=["zipf", "lognormal", "uniform", "exp"], default="zipf")
    g.add_argument("--sd-max", type=int, default=50000, help="maior stack distance finita")
    g.add_argument("--sd-beta", type=float, default=0.8, help="expoente (zipf) / escala (exp)")
    g.add_argument("--sd-mu", type=float, default=6.0, help="mu do lognormal (em log(d+1))")
    g.add_argument("--sd-sigma", type=float, default=1.5)
    g.add_argument("--cold-prob", type=float, default=0.02,
                   help="P(SD = infinito) = taxa de objetos novos / one-timers")
    g.add_argument("--sd-file", default="",
                   help="arquivo com a SUA P(s): linhas 'd prob', 'a-b prob', 'inf prob' "
                        "(substitui --sd-dist, --sd-max e --cold-prob)")
    g.add_argument("--emit-warmup", action="store_true",
                   help="escreve antes do trace um prefixo que aquece o LRU; ver --skip")
    # irm
    g.add_argument("--objects", type=int, default=20000)
    g.add_argument("--alpha", type=float, default=1.0)

    a = sub.add_parser("analyze", help="mede SD, MRC LRU e MRC FIFO de um trace")
    a.add_argument("trace")
    a.add_argument("--mrc-points", type=int, default=10)
    a.add_argument("--shards", type=float, default=0.0, help="taxa R de amostragem SHARDS")
    a.add_argument("--no-fifo", action="store_true")
    a.add_argument("--skip", type=int, default=0,
                   help="as primeiras K linhas so aquecem o cache; ficam fora das estatisticas")
    a.add_argument("--sizes", default="",
                   help="tamanhos de cache (em objetos) para a MRC, ex.: 1,10,100,1000")

    args = p.parse_args()

    if args.cmd == "gen":
        fh = sys.stdout if args.out == "-" else open(args.out, "w")
        buf = []
        def out(o):
            buf.append(str(o))
            if len(buf) >= 65536:
                fh.write("\n".join(buf) + "\n")
                buf.clear()
        (gen_lrusm if args.model == "lrusm" else gen_irm)(args, out)
        if buf:
            fh.write("\n".join(buf) + "\n")
        if fh is not sys.stdout:
            fh.close()
        return

    trace = [l.strip() for l in open(args.trace) if l.strip()]
    skip = args.skip
    scale = 1.0
    if args.shards > 0:
        full = len(trace)
        trace, idx = shards_filter(trace, args.shards)
        skip = sum(1 for i in idx if i < args.skip)
        scale = 1.0 / args.shards
        print("SHARDS R=%g : %d -> %d requisicoes (fator de escala %.1fx)"
              % (args.shards, full, len(trace), scale))
        if len(trace) <= skip:
            raise SystemExit("amostra vazia: aumente R")
    if skip >= len(trace):
        raise SystemExit("--skip maior que o trace")

    sds = stack_distances(trace)[skip:]      # o prefixo aquece a pilha, mas nao conta
    ev = trace[skip:]
    uniq = len(set(ev))
    print("requisicoes=%d  objetos unicos=%d%s" % (len(ev), uniq,
          ("  (ignoradas %d de aquecimento)" % skip) if skip else ""))
    freq = Counter(ev)
    ones = sum(1 for v in freq.values() if v == 1)
    print("one-timers=%d (%.2f%% dos objetos)" % (ones, 100 * ones / uniq))
    print("Histograma de stack distance%s:" % (" (amostrado)" if scale > 1 else ""))
    for l in hist_lines(sds):
        print(l)

    fin = sorted(d for d in sds if d >= 0)
    if fin:
        if args.sizes:
            sizes = sorted({max(1, int(round(int(x) / scale))) for x in args.sizes.split(",")})
        else:
            top = max(fin[int(0.99 * len(fin))], 8)
            sizes = sorted({max(1, int(top ** ((i + 1) / args.mrc_points)))
                            for i in range(args.mrc_points)})
        lru = mrc_lru_from_sd(sds, sizes)
        fifo = None if args.no_fifo else mrc_fifo(trace, sizes, skip)
        print("\nMRC (miss ratio)%s:" % ("  [tamanhos ja reescalados por 1/R]" if scale > 1 else ""))
        print("  %12s  %10s  %10s" % ("cache(objs)", "LRU", "FIFO"))
        for i, c in enumerate(sizes):
            f = "%10.4f" % fifo[i] if fifo else "%10s" % "-"
            print("  %12d  %10.4f  %s" % (int(c * scale), lru[i], f))


if __name__ == "__main__":
    main()
