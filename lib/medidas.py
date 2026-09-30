#!/usr/bin/env python3
"""
medidas.py - o que se mede num trace: stack distance, curva de hit rate LRU, footprint e
frequencia por objeto.

E o instrumento comum as partes do laboratorio. A geracao usa para conferir a carga contra a
distribuicao pedida; a amostragem usa para medir as amostras e a carga inteira com a mesma regua.
Nada aqui depende de como o trace foi feito: entra uma lista de ids, sai a medida.
"""
import bisect, math

import genwl


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


def curva_footprint(ev):
    """Footprint exato: fp(w) = objetos distintos numa janela de w requisicoes, em media
    sobre TODAS as janelas de tamanho w do trace (nao sobre uma amostra delas).

    A conta e feita pelo avesso, como em Xiang et al. (ASPLOS 2013): uma janela deixa de
    ver um objeto exatamente quando cabe inteira dentro de um intervalo em que ele nao
    aparece. Um intervalo de L posicoes acomoda L - w + 1 janelas de tamanho w, entao

        fp(w) = m - (soma de max(0, L - w + 1) sobre todos os intervalos) / (n - w + 1)

    com m = objetos distintos da carga inteira. Os intervalos de cada objeto sao o trecho
    antes da estreia dele, os buracos entre acessos consecutivos e o trecho depois do
    ultimo acesso. Com o histograma desses L e duas somas de sufixo, cada fp(w) sai em
    tempo logaritmico, para qualquer w de 1 ate n.

    Duas consequencias uteis: fp(1) = 1 e fp(n) = m. O extremo direito da curva e o numero
    de objetos distintos da carga -- o footprint tem um valor unico so quando a janela e a
    carga inteira. E, por nao amostrar nada, a medida nao depende de semente.

    Devolve (fp, m)."""
    n = len(ev)
    ultimo, lacunas = {}, {}
    for p, o in enumerate(ev):
        L = p - ultimo.get(o, -1) - 1
        if L:
            lacunas[L] = lacunas.get(L, 0) + 1
        ultimo[o] = p
    for p in ultimo.values():
        L = n - 1 - p
        if L:
            lacunas[L] = lacunas.get(L, 0) + 1
    m = len(ultimo)
    tam = sorted(lacunas)
    quantas = [0] * (len(tam) + 1)     # quantos intervalos com L >= tam[k]
    soma_L = [0] * (len(tam) + 1)      # e a soma dos L deles
    for k in range(len(tam) - 1, -1, -1):
        quantas[k] = quantas[k + 1] + lacunas[tam[k]]
        soma_L[k] = soma_L[k + 1] + lacunas[tam[k]] * tam[k]

    def fp(w):
        if not 1 <= w <= n:
            raise ValueError("janela fora do trace: %r" % w)
        k = bisect.bisect_left(tam, w)
        cegas = soma_L[k] - (w - 1) * quantas[k]   # janelas que nao veem um dado objeto
        return m - cegas / (n - w + 1)

    return fp, m


def medir_frequencia(ev):
    """Contagem de requisicoes por objeto -- a terceira vista da mesma localidade.

    Nao e parametro do gerador: no LRU Stack Model o que se sorteia e a PROFUNDIDADE, nao
    o objeto, entao a popularidade e consequencia da distribuicao de stack distance, do
    mesmo jeito que o footprint. Por isso entra no relatorio como medida, sem valor teorico
    ponto a ponto ao lado. A unica ancora exata e a media: um objeto novo nasce a cada
    1/P(inf) requisicoes, entao cada objeto rende em media 1/P(inf) pedidos.

    A contagem e feita no trace ja sem o prefixo de aquecimento, como todas as outras
    medidas -- o que aparece aqui e o que a carga pede, sem correcao de borda."""
    n = len(ev)
    cont = {}
    for o in ev:
        cont[o] = cont.get(o, 0) + 1
    asc = sorted(cont.values())              # contagens em ordem crescente
    m = len(asc)
    acum, soma = [], 0
    for f in reversed(asc):                  # do objeto mais pedido para o menos pedido
        soma += f
        acum.append(soma)
    topo = lambda frac: acum[max(1, int(round(frac * m))) - 1] / n
    hist, lim = [], 1
    while lim <= asc[-1]:
        prox = lim * 2
        c = bisect.bisect_left(asc, prox) - bisect.bisect_left(asc, lim)
        hist.append((lim, min(prox - 1, asc[-1]), c, c / m))
        lim = prox
    return {"objetos": m, "media": n / m, "maxima": asc[-1],
            "um_hit": bisect.bisect_right(asc, 1) / m,
            "top1": topo(0.01), "top10": topo(0.10),
            "curva": [(k, asc[m - k], acum[k - 1] / n) for k in grade_log(m, 30)],
            "hist": hist}


def medir(trace, prefixo=0, d_lim=None):
    """Todas as medidas de um trace (lista de ids), ignorando as 'prefixo' primeiras linhas.

    O prefixo aquece a pilha LRU mas fica fora das contas: sem ele (prefixo = 0), a primeira
    aparicao de cada objeto conta como objeto novo -- que e o que acontece num simulador que
    comeca com o cache vazio.

    d_lim e o limite (exclusivo) do histograma de SD. Na geracao e o d_max, que nenhum reuso
    passa; sem ele, vai ate a maior SD medida.

    hit(C) e cdf(x) voltam como funcoes, para quem chama escolher a grade:
        hit(C) = fracao das requisicoes que acertam num LRU de C objetos (reusos com d < C)
        cdf(x) = fracao dos reusos com d < x"""
    sds = genwl.stack_distances(trace)[prefixo:]
    n = len(sds)
    fin = sorted(d for d in sds if d >= 0)
    r = len(fin)
    if r == 0:
        raise ValueError("trace sem reusos")
    pct = lambda q: fin[min(r - 1, int(q * (r - 1)))]
    if d_lim is None:
        d_lim = fin[-1] + 1

    # histograma de SD em faixas de uma oitava (x2). A primeira faixa e so o d = 0,
    # que e a moda quando a localidade e forte e nao pode ficar de fora da soma.
    zeros = bisect.bisect_left(fin, 1)
    hist = [(0, 0, zeros, zeros / r)]
    lim = 1
    while lim < d_lim:
        prox = lim * 2
        c = bisect.bisect_left(fin, prox) - bisect.bisect_left(fin, lim)
        hist.append((lim, min(prox, d_lim) - 1, c, c / r))
        lim = prox

    ev = trace[prefixo:]
    fp_de, distintos = curva_footprint(ev)
    # grade log de janelas, com as decadas redondas garantidas para dar pontos de referencia
    # legiveis, e a carga inteira no extremo direito: fp(n) e o numero de objetos distintos.
    decadas = {10 ** k for k in range(len(str(len(ev))))}     # 1, 10, 100, ... <= len(ev)
    janelas = sorted(set(grade_log(len(ev), 25)) | decadas)

    return {
        "requisicoes": n, "prefixo": prefixo, "reusos": r, "p_inf_medido": (n - r) / n,
        "p25": pct(.25), "p50": pct(.50), "p75": pct(.75), "p90": pct(.90), "p99": pct(.99),
        "sd_max": fin[-1],
        "hit": lambda C: bisect.bisect_left(fin, C) / n,
        "cdf": lambda x: bisect.bisect_left(fin, x) / r,
        "hist": hist,
        "distintos": distintos,
        "fp": [(j, fp_de(j), fp_de(j) / j) for j in janelas],
        "fp_1k": fp_de(1000) if len(ev) >= 1000 else None,
        "freq": medir_frequencia(ev),
    }
