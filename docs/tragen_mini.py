#!/usr/bin/env python3
"""
tragen_mini.py - reimplementacao didatica do nucleo do TRAGEN (Sabnis &
Sitaraman, IMC 2021, Algoritmo 2), para entender e verificar o metodo.

NAO substitui o TRAGEN: nao le os arquivos da Akamai, nao faz mistura de
classes (FD calculus) e nao usa a janela de popularidade do codigo atual.
Implementa apenas a ideia central: "agendar para frente".

  lista C = fila de objetos, na ordem em que SERAO requisitados
  a cada passo:
     1. emite o objeto da frente de C
     2. sorteia s ~ P(s)          (s = stack distance em BYTES, ou inf)
     3. s finito : reinsere o objeto a ~s bytes da frente
        s = inf  : o objeto nunca mais volta; entram objetos novos no fim

Compara com o "LRUSM adaptado a bytes" (olhar para tras), que o paper
mostra que falha por vies de tamanho.

  python3 tragen_mini.py passo-a-passo   # exemplo pequeno, estado a estado
  python3 tragen_mini.py comparar        # TRAGEN x LRUSM-bytes, 200k reqs
"""
import bisect, random, sys
from collections import OrderedDict

INF = -1


# ----------------------------------------------------------------- modelo
def modelo_exemplo():
    """Um 'footprint descriptor' de brinquedo (marginal P(s)), em unidades de byte."""
    tamanhos = [1, 4, 16, 64, 256]                 # SZ(z): distribuicao de tamanho
    p_tam    = [0.40, 0.30, 0.15, 0.10, 0.05]
    gran     = 50                                  # granularidade do bucket de s
    s_max    = 5000
    p_inf    = 0.10                                # P(s = inf): 1a/ultima referencia
    buckets  = list(range(0, s_max + 1, gran))
    w        = [(b / gran + 1.0) ** -0.9 for b in buckets]
    k        = (1 - p_inf) / sum(w)
    P        = [(b, x * k) for b, x in zip(buckets, w)] + [(INF, p_inf)]
    return P, tamanhos, p_tam, gran


def amostrador(P, gran, rnd):
    chaves = [s for s, _ in P]
    pesos  = [p for _, p in P]
    def sample():
        s = rnd.choices(chaves, weights=pesos)[0]
        # como o codigo real: espalha uniforme dentro do bucket [s, s+gran)
        return s if s == INF else rnd.randint(s, s + gran - 1)
    return sample


# -------------------------------------------------- gerador TRAGEN (frente)
def gera_tragen(P, tamanhos, p_tam, gran, n, seed=1, trace_passos=None):
    rnd = random.Random(seed)
    sample = amostrador(P, gran, rnd)
    s_max = max(s for s, _ in P if s != INF)
    C, prox = [], 0                                 # C: lista de (id, tamanho)

    def novo():
        nonlocal prox
        prox += 1
        return (prox, rnd.choices(tamanhos, weights=p_tam)[0])

    def total(): return sum(z for _, z in C)
    while total() < s_max:                          # Fase 1: inicializacao
        C.append(novo())

    out = []
    for i in range(n):                              # Fase 2: geracao
        s = sample() if trace_passos is None else trace_passos[i]
        while s != INF and s >= sum(z for _, z in C[1:]):
            s = sample()                            # nao cabe na lista: sorteia de novo
        obj = C.pop(0)
        out.append(obj)                             # 1. emite a frente
        if s != INF:                                # 3a. reagenda a ~s bytes
            acc, j = 0, 0
            while j < len(C) and acc + C[j][1] <= s:
                acc += C[j][1]; j += 1
            if j < len(C):                          # s cai dentro do objeto C[j]:
                frac = (s - acc) / C[j][1]          # arredondamento estocastico,
                if rnd.random() < frac:             # como o insertAt() real
                    j += 1
            C.insert(j, obj)
        else:                                       # 3b. aposenta o objeto
            while total() < s_max:
                C.append(novo())
        if trace_passos is not None:
            yield i, obj, s, list(C)
    if trace_passos is None:
        yield out


# ------------------------------------ LRUSM adaptado a bytes (olhar p/ tras)
def gera_lrusm_bytes(P, tamanhos, p_tam, gran, n, seed=1):
    rnd = random.Random(seed)
    sample = amostrador(P, gran, rnd)
    s_max = max(s for s, _ in P if s != INF)
    pilha, prox = [], 0
    def novo():
        nonlocal prox
        prox += 1
        return (prox, rnd.choices(tamanhos, weights=p_tam)[0])
    while sum(z for _, z in pilha) < s_max:
        pilha.append(novo())
    out = []
    for _ in range(n):
        s = sample()
        if s == INF:
            obj = novo()
        else:                                       # o objeto que "cobre" o byte s
            acc, j = 0, 0
            while j < len(pilha) - 1 and acc + pilha[j][1] <= s:
                acc += pilha[j][1]; j += 1
            obj = pilha.pop(j)
        pilha.insert(0, obj)
        out.append(obj)
    return out


# ----------------------------------------------------------------- medicao
def mede(trace, caches):
    """Para cada reuso: s = bytes dos objetos distintos pedidos ENTRE os dois
    pedidos (a mesma grandeza que o gerador sorteia). Um cache LRU de c bytes
    acerta quando s + tamanho do proprio objeto <= c."""
    lru = OrderedDict()                 # id -> tamanho; ultimo = mais recente
    sds = []
    for oid, z in trace:
        if oid in lru:
            acc = 0
            for k in reversed(lru):     # soma bytes acima dele na pilha
                if k == oid: break
                acc += lru[k]
            sds.append((acc, z))
            lru.move_to_end(oid)
        else:
            sds.append((None, z))
            lru[oid] = z
    n = len(trace); nb = sum(z for _, z in trace)
    ps   = [sum(1 for s, _ in sds if s is not None and s <= c) / n for c in caches]
    rhrc = [sum(1 for s, z in sds if s is not None and s + z <= c) / n for c in caches]
    bhrc = [sum(z for s, z in sds if s is not None and s + z <= c) / nb for c in caches]
    return ps, rhrc, bhrc, nb / n, sum(1 for s, _ in sds if s is None) / n


def alvo_ps(P, gran, caches):
    """P(s <= c) do modelo, com s uniforme dentro de cada bucket [b, b+gran)."""
    out = []
    for c in caches:
        acc = 0.0
        for b, p in P:
            if b != INF:
                acc += p * min(1.0, max(0.0, (c - b + 1) / gran))
        out.append(acc)
    return out


# -------------------------------------------------------------------- main
def passo_a_passo():
    """Exemplo conferivel a mao: objetos com nome e s escolhidos nas fronteiras."""
    tam = {"A": 2, "B": 3, "C": 1, "D": 4, "E": 3}
    C = ["A", "B", "C", "D"]                        # 10 bytes = maior s do modelo
    novos = iter(["E"])
    passos = [4, INF, 6, 5, 3, 2]
    fmt = lambda L: "[ " + "  ".join(f"{o}({tam[o]})" for o in L) + " ]"
    print("inicio   :", fmt(C), "  <- ordem em que os objetos SERAO pedidos")
    trace, ultimo = [], {}
    for i, s in enumerate(passos, 1):
        o = C.pop(0)
        if o in ultimo:
            meio = set(trace[ultimo[o] + 1:])
            sd = sum(tam[x] for x in meio)
            nota = f"  reuso de {o}: entre os dois pedidos vieram {sorted(meio)} = {sd} bytes"
        else:
            nota = f"  primeira vez que {o} aparece no trace (stack distance = inf)"
        ultimo[o] = len(trace); trace.append(o)
        if s == INF:
            while sum(tam[x] for x in C) < 10:
                C.append(next(novos))
            lab = "inf  -> sai da lista para sempre; entra objeto novo no fim"
        else:
            acc, j = 0, 0
            while j < len(C) and acc + tam[C[j]] <= s:
                acc += tam[C[j]]; j += 1
            C.insert(j, o)
            lab = f"{s} bytes -> reinserido com {acc} bytes a frente"
        print(f"passo {i}  : emite {o}; s = {lab}")
        print(f"           {fmt(C)}")
        print(f"         {nota}")
    print("\ntrace gerado:", " ".join(trace))


def comparar():
    P, tam, ptam, gran = modelo_exemplo()
    N = 200_000
    caches = [50, 200, 800, 2000, 5000]
    media_sz = sum(t * p for t, p in zip(tam, ptam))
    enviesada = sum(t * t * p for t, p in zip(tam, ptam)) / media_sz
    print(f"SZ: media por objeto = {media_sz:.1f} B ; media 'enviesada por tamanho' = {enviesada:.1f} B\n")
    tr = next(gera_tragen(P, tam, ptam, gran, N, seed=11))
    lr = gera_lrusm_bytes(P, tam, ptam, gran, N, seed=11)
    alvo = alvo_ps(P, gran, caches)
    s1, r1, b1, m1, c1 = mede(tr, caches)
    s2, r2, b2, m2, c2 = mede(lr, caches)
    print(f"{'':24}{'modelo':>8}{'TRAGEN':>10}{'LRUSM-bytes':>13}")
    print(f"{'tamanho medio por req':24}{media_sz:>8.1f}{m1:>10.1f}{m2:>13.1f}")
    print(f"{'fracao de 1a referencia':24}{0.1:>8.3f}{c1:>10.3f}{c2:>13.3f}")
    print("-- a distribuicao de s saiu como pedida?")
    for c, a, x, y in zip(caches, alvo, s1, s2):
        print(f"{'P(s <= ' + str(c) + ' B)':24}{a:>8.3f}{x:>10.3f}{y:>13.3f}")
    print("-- e o cache LRU real (acerto se s + tamanho <= c)?")
    for c, x, y in zip(caches, r1, r2):
        print(f"{'RHR  c = ' + str(c) + ' B':24}{'':>8}{x:>10.3f}{y:>13.3f}")
    for c, x, y in zip(caches, b1, b2):
        print(f"{'BHR  c = ' + str(c) + ' B':24}{'':>8}{x:>10.3f}{y:>13.3f}")


if __name__ == "__main__":
    {"passo-a-passo": passo_a_passo, "comparar": comparar}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
