#!/usr/bin/env python3
"""
graficos.py - os graficos da analise de amostragem, em facetas.

Um SVG por metrica. Cada figura e uma grade: uma LINHA por tecnica de amostragem (sis-p01 ...
jan-p20-t10k), uma COLUNA por nivel de stack distance da carga (baixa, media, alta), e em cada
faceta a carga original (completa) contra a amostrada. Os eixos sao os mesmos em todas as
facetas de uma figura, para que a comparacao entre linhas e entre colunas seja direta.

Le so os CSVs de analise/ e o manifesto da fase; roda sozinho ou no fim do pipeline:

    python3 graficos.py --fase a01

Saidas em analise/: hrc_<fase>.svg, sd_cdf_<fase>.svg, sd_histograma_<fase>.svg,
footprint_<fase>.svg, frequencia_<fase>.svg, frequencia_hist_<fase>.svg.
Biblioteca padrao apenas, como o resto do laboratorio.
"""
import argparse, csv, json, math, os

# cores validadas (dataviz: validate_palette.js, modo claro, PASS em todos os checks)
SUPERFICIE = "#fcfcfb"
TEXTO, TEXTO_2, TEXTO_3 = "#0b0b0b", "#52514e", "#7a7974"
GRADE, EIXO = "#e7e6e2", "#c9c8c2"
COR_ORIG, COR_AMOS = "#2a78d6", "#eb6834"      # original: azul continuo; amostrada: laranja tracejado
TRACO_AMOS = "5 3"

FW, FH = 210, 118            # uma faceta
GX, GY = 14, 16              # espaco entre facetas
ML, MT, MB, MR = 190, 128, 30, 18


# --------------------------------------------------------------- leitura
def le_csv(caminho):
    with open(caminho, newline="") as fh:
        return list(csv.DictReader(fh))


def rotulo_tecnica(t):
    """sis-p10 -> 'sistemática 10%'; jan-p10-t1k -> 'janela 10% · take 1k'."""
    p = t.split("-")
    taxa = "%d%%" % int(p[1][1:])
    if p[0] == "sis":
        return "sistemática " + taxa
    return "janela %s · take %s" % (taxa, p[2][1:])


def beta_br(b):
    t = "%g" % b
    return (t if "." in t else t + ".0").replace(".", ",")


def rotulo_cenario(c):
    """'SD baixa · β 1,5' quando o cenario tem nome de nivel (fase f03); senao so 'β 1,5'."""
    if c["nome"] in ("baixa", "media", "alta"):
        return "SD %s · β %s" % (c["nome"].replace("media", "média"), beta_br(c["beta"]))
    return "β %s" % beta_br(c["beta"])


def num_br(v):
    if v >= 1e6:
        return "%gM" % (v / 1e6)
    if v >= 1e3:
        return "%gk" % (v / 1e3)
    return ("%g" % v).replace(".", ",")


# --------------------------------------------------------------- escalas
class Escala:
    def __init__(self, lo, hi, tipo, px0, px1):
        self.tipo, self.px0, self.px1 = tipo, px0, px1
        if tipo == "log":
            self.lo, self.hi = math.log10(lo), math.log10(hi)
        else:
            self.lo, self.hi = lo, hi

    def __call__(self, v):
        x = math.log10(v) if self.tipo == "log" else v
        return self.px0 + (x - self.lo) / ((self.hi - self.lo) or 1) * (self.px1 - self.px0)

    def ticks(self):
        if self.tipo == "log":
            return [10 ** k for k in range(math.ceil(self.lo - 1e-9), math.floor(self.hi + 1e-9) + 1)]
        passo = [0.05, 0.1, 0.2, 0.25, 0.5, 1][min(5, sum(1 for s in (0.25, 0.5, 1, 1.2, 2.5)
                                                          if self.hi > s))]
        return [round(i * passo, 4) for i in range(int(self.hi / passo + 1e-9) + 1)]


# --------------------------------------------------------------- figura
def figura(titulo, subtitulo, linhas, colunas, desenha, eixo_x, eixo_y, nota=None, legenda="linha"):
    """Monta a grade. desenha(r, c, x0, y0) devolve os elementos SVG da faceta (r, c).
    eixo_x / eixo_y sao funcoes (x0|y0) -> [(pixel, texto)] para os rotulos dos ticks."""
    W = ML + len(colunas) * FW + (len(colunas) - 1) * GX + MR
    H = MT + len(linhas) * FH + (len(linhas) - 1) * GY + MB
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SUPERFICIE),
         '<text x="16" y="28" font-size="17" font-weight="600" fill="%s">%s</text>' % (TEXTO, titulo),
         ] + ['<text x="16" y="%d" font-size="12" fill="%s">%s</text>' % (48 + 16 * i, TEXTO_2, t)
              for i, t in enumerate(subtitulo.split("\n"))]
    # legenda: sempre presente, com a amostra do traco
    lx = 16
    itens = legenda if isinstance(legenda, list) else [
        (legenda, COR_ORIG, "", "original (carga completa)"),
        (legenda, COR_AMOS, TRACO_AMOS, "amostrada")]
    for tipo, cor, traco, nome in itens:
        if tipo == "barra":                       # o simbolo da legenda e o da marca do grafico
            s.append('<rect x="%d" y="78" width="12" height="12" rx="2" fill="%s"/>' % (lx + 14, cor))
        else:
            s.append('<line x1="%d" y1="84" x2="%d" y2="84" stroke="%s" stroke-width="2.5"%s/>'
                     % (lx, lx + 26, cor, ' stroke-dasharray="%s"' % traco if traco else ""))
        s.append('<text x="%d" y="88" font-size="12" fill="%s">%s</text>' % (lx + 32, TEXTO, nome))
        lx += 32 + 8 * len(nome) + 22
    for c, nome in enumerate(colunas):
        x0 = ML + c * (FW + GX)
        s.append('<text x="%.1f" y="%d" font-size="12.5" font-weight="600" text-anchor="middle" '
                 'fill="%s">%s</text>' % (x0 + FW / 2, MT - 12, TEXTO, nome))
    for r, nome in enumerate(linhas):
        y0 = MT + r * (FH + GY)
        s.append('<text x="%d" y="%.1f" font-size="12" text-anchor="end" fill="%s">%s</text>'
                 % (ML - 42, y0 + FH / 2 + 4, TEXTO, nome))
        for c in range(len(colunas)):
            x0 = ML + c * (FW + GX)
            s.append('<g>')
            s.extend(desenha(r, c, x0, y0))
            s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s"/>'
                     % (x0, y0, FW, FH, EIXO))
            s.append('</g>')
            if nota:
                t = nota(r, c)
                if t:
                    s.append('<text x="%d" y="%d" font-size="10.5" text-anchor="end" fill="%s" '
                             'stroke="%s" stroke-width="3.5" paint-order="stroke">%s</text>'
                             % (x0 + FW - 5, y0 + FH - 7, TEXTO, SUPERFICIE, t))
        for py, txt in eixo_y(y0):
            s.append('<text x="%d" y="%.1f" font-size="10" text-anchor="end" fill="%s">%s</text>'
                     % (ML - 5, py + 3.5, TEXTO_3, txt))
    yb = MT + len(linhas) * FH + (len(linhas) - 1) * GY
    for c in range(len(colunas)):
        x0 = ML + c * (FW + GX)
        for px, txt in eixo_x(x0):
            # o primeiro e o ultimo rotulo encostam na faceta vizinha: alinha para dentro
            ancora = "start" if px - x0 < 8 else "end" if x0 + FW - px < 8 else "middle"
            s.append('<text x="%.1f" y="%d" font-size="10" text-anchor="%s" fill="%s">%s</text>'
                     % (px, yb + 14, ancora, TEXTO_3, txt))
    s.append('</svg>')
    return "\n".join(s)


def polilinha(pts, cor, traco=""):
    if len(pts) < 2:
        return []
    d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", x, y) for i, (x, y) in enumerate(pts))
    return ['<path d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"%s/>'
            % (d, cor, ' stroke-dasharray="%s"' % traco if traco else "")]


def grade_linhas(x0, y0, ex, ey, xs_ticks, ys_ticks):
    g = []
    for t in ys_ticks:
        py = ey(t) + y0
        g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (x0, py, x0 + FW, py, GRADE))
    for t in xs_ticks:
        px = ex(t) + x0
        g.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>' % (px, y0, px, y0 + FH, GRADE))
    return g


# --------------------------------------------------------------- tipos de grafico
def curvas(dados, tecnicas, cenarios, x_tipo, y_tipo, y_fixo=None):
    """dados[(cen, tec)] = (pontos_orig, pontos_amos), cada um [(x, y)].
    Devolve (desenha, eixo_x, eixo_y) com escalas compartilhadas por toda a figura."""
    xs = [x for par in dados.values() for pts in par for x, _ in pts if x > 0]
    ys = [y for par in dados.values() for pts in par for _, y in pts if y_tipo == "lin" or y > 0]
    ex = Escala(min(xs), max(xs), x_tipo, 0, FW)
    if y_fixo:
        ey = Escala(y_fixo[0], y_fixo[1], y_tipo, FH, 0)
    elif y_tipo == "log":
        # um respiro abaixo do piso: valores iguais a 1 (objeto pedido uma vez) nao somem na moldura
        ey = Escala(10 ** (math.floor(math.log10(min(ys))) - 0.15),
                    10 ** math.ceil(math.log10(max(ys))), "log", FH, 0)
    else:
        ey = Escala(0, max(ys) * 1.05, "lin", FH, 0)
    xt, yt = ex.ticks(), ey.ticks()
    if x_tipo == "log" and len(xt) > 4:            # num facetas de 210 px, uma decada sim, outra nao
        xt_rot = xt[::2]
    else:
        xt_rot = xt

    def desenha(r, c, x0, y0):
        orig, amos = dados[(cenarios[c], tecnicas[r])]
        f = lambda pts: [(ex(x) + x0, ey(y) + y0) for x, y in pts
                         if x > 0 and (y_tipo == "lin" or y > 0)]
        return (grade_linhas(x0, y0, ex, ey, xt, yt)
                + polilinha(f(orig), COR_ORIG) + polilinha(f(amos), COR_AMOS, TRACO_AMOS))

    eixo_x = lambda x0: [(ex(t) + x0, num_br(t)) for t in xt_rot]
    eixo_y = lambda y0: [(ey(t) + y0, num_br(t)) for t in yt]
    return desenha, eixo_x, eixo_y


def barras(dados, tecnicas, cenarios):
    """Histograma em faixas de oitava. dados[(cen, tec)] = (dict orig, dict amos), faixa_de -> fracao.
    Cada faixa e uma categoria; as duas barras lado a lado, 2 px de superficie entre elas."""
    faixas = sorted({k for par in dados.values() for h in par for k in h})
    n = len(faixas)
    topo = max(v for par in dados.values() for h in par for v in h.values())
    ey = Escala(0, topo * 1.05, "lin", FH, 0)
    yt = ey.ticks()
    larg = FW / n
    b = max(1.0, (larg - 2 - 1) / 2)             # 2 px entre grupos, 1 px entre as barras do par

    def desenha(r, c, x0, y0):
        orig, amos = dados[(cenarios[c], tecnicas[r])]
        s = grade_linhas(x0, y0, None, ey, [], yt)
        for i, f in enumerate(faixas):
            gx = x0 + i * larg + 1
            for j, (h, cor) in enumerate(((orig, COR_ORIG), (amos, COR_AMOS))):
                v = h.get(f, 0)
                if v <= 0:
                    continue
                y = ey(v) + y0
                s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"%s/>'
                         % (gx + j * (b + 1), y, b, y0 + FH - y, cor,
                            ' fill-opacity="0.85"' if j else ""))
        return s

    def eixo_x(x0):
        out = []
        for i, f in enumerate(faixas):
            if f == 0 or (f >= 1 and round(math.log2(f)) % 3 == 0):
                out.append((x0 + (i + 0.5) * larg, num_br(f)))
        return out

    eixo_y = lambda y0: [(ey(t) + y0, num_br(t)) for t in yt]
    return desenha, eixo_x, eixo_y


# --------------------------------------------------------------- resumos por beta
TAXA_CORES = {1: "#86b6ef", 10: "#2a78d6", 20: "#104281"}   # rampa ordinal azul (validada)
MAPA_CORES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MAPA_LIMITES = [0.02, 0.05, 0.10, 0.20, 0.30, 0.45]           # fracao -> classe de cor


def erro_por_beta(med, man, aid, titulo=None, subtitulo=None, medidas=None, ymax_fixo=None,
                  referencia=False):
    """Uma medida contra beta: um painel por familia de tecnica (colunas) e por medida (linhas),
    uma linha por taxa. O eixo x vai do beta mais alto (SD mais baixa) ao mais baixo, na mesma
    ordem das colunas dos graficos em facetas. Por padrao, o erro da curva de hit; com
    referencia=True, desenha tambem o valor da carga completa (linha cinza tracejada)."""
    betas = {c["sufixo"]: c["beta"] for c in man["cenarios"]}
    bmax, bmin = max(betas.values()), min(betas.values())
    fams = [("sistemática", lambda t: t.startswith("sis")),
            ("janela · take 1k", lambda t: t.endswith("t1k")),
            ("janela · take 10k", lambda t: t.endswith("t10k"))]
    medidas = medidas or [("erro médio absoluto", "erro_medio_abs_hrc_vs_completa"),
                          ("erro máximo", "erro_max_hrc_vs_completa")]
    titulo = titulo or "Erro da curva de hit rate por nível de stack distance"
    subtitulo = subtitulo or ("y: erro contra a carga completa · x: β da carga, do mais alto (SD "
                              "mais baixa) ao mais baixo (SD mais alta)")
    nm = len(medidas)
    PW, PH, GX, GY = 300, 190, 54, 46
    L, T, B, R = 70, 118, 46, 40
    W = L + 3 * PW + 2 * GX + R
    H = T + nm * PH + (nm - 1) * GY + B
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SUPERFICIE),
         '<text x="16" y="28" font-size="17" font-weight="600" fill="%s">%s · fase %s</text>'
         % (TEXTO, titulo, aid),
         '<text x="16" y="48" font-size="12" fill="%s">%s</text>' % (TEXTO_2, subtitulo)]
    lx = 16
    for pct, cor in sorted(TAXA_CORES.items()):
        s.append('<line x1="%d" y1="72" x2="%d" y2="72" stroke="%s" stroke-width="2.5"/>'
                 '<circle cx="%d" cy="72" r="4" fill="%s" stroke="%s" stroke-width="2"/>'
                 % (lx, lx + 26, cor, lx + 13, cor, SUPERFICIE))
        s.append('<text x="%d" y="76" font-size="12" fill="%s">taxa %d%%</text>' % (lx + 32, TEXTO, pct))
        lx += 110
    if referencia:
        s.append('<line x1="%d" y1="72" x2="%d" y2="72" stroke="%s" stroke-width="2" stroke-dasharray="5 3"/>'
                 % (lx, lx + 26, DIAG))
        s.append('<text x="%d" y="76" font-size="12" fill="%s">carga completa</text>' % (lx + 32, TEXTO))
    linhas_csv = [l for l in med if l["amostra"] != "completa"]
    completas = [l for l in med if l["amostra"] == "completa"]
    for r, (mrot, mcol) in enumerate(medidas):
        ymax = ymax_fixo or math.ceil(max(float(l[mcol]) for l in linhas_csv) * 10 + 1e-9) / 10
        y0 = T + r * (PH + GY)
        for c, (frot, ftem) in enumerate(fams):
            x0 = L + c * (PW + GX)
            ex = lambda b: x0 + (bmax - b) / ((bmax - bmin) or 1) * PW
            ey = lambda v: y0 + PH - v / ymax * PH
            if r == 0:
                s.append('<text x="%.1f" y="%d" font-size="12.5" font-weight="600" text-anchor="middle" '
                         'fill="%s">%s</text>' % (x0 + PW / 2, T - 12, TEXTO, frot))
            for k in range(0, int(round(ymax * 10)) + 1):
                v = k / 10
                s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (x0, ey(v), x0 + PW, ey(v), GRADE))
                if c == 0:
                    s.append('<text x="%d" y="%.1f" font-size="10" text-anchor="end" fill="%s">%s</text>'
                             % (x0 - 6, ey(v) + 3.5, TEXTO_3, num_br(v)))
            for b in sorted(set(betas.values())):
                s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>' % (ex(b), y0, ex(b), y0 + PH, GRADE))
                if r == nm - 1 and (b * 2) == int(b * 2):
                    s.append('<text x="%.1f" y="%d" font-size="10" text-anchor="middle" fill="%s">%s</text>'
                             % (ex(b), y0 + PH + 15, TEXTO_3, beta_br(b)))
            s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s"/>' % (x0, y0, PW, PH, EIXO))
            if c == 0:
                s.append('<text x="16" y="%.1f" font-size="12" fill="%s" transform="rotate(-90 16 %.1f)" '
                         'text-anchor="middle">%s</text>' % (y0 + PH / 2, TEXTO, y0 + PH / 2, mrot))
            if referencia:
                pr = sorted(((betas[l["cenario"]], float(l[mcol])) for l in completas), reverse=True)
                s.append('<path d="%s" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="5 3"/>'
                         % (" ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", ex(b), ey(v))
                                     for i, (b, v) in enumerate(pr)), DIAG))
            ultimos = []
            for pct, cor in sorted(TAXA_CORES.items()):
                pts = sorted(((betas[l["cenario"]], float(l[mcol])) for l in linhas_csv
                              if ftem(l["amostra"]) and int(l["taxa_pct"]) == pct), reverse=True)
                if not pts:
                    continue
                d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", ex(b), ey(v)) for i, (b, v) in enumerate(pts))
                s.append('<path d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"/>' % (d, cor))
                for b, v in pts:
                    s.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="%s" stroke-width="2">'
                             '<title>%s · taxa %d%% · β %s: %s</title></circle>'
                             % (ex(b), ey(v), cor, SUPERFICIE, frot, pct, beta_br(b), num_br(round(v, 3))))
                ultimos.append([ey(pts[-1][1]), "%d%%" % pct])
            ultimos.sort()                              # rotulos diretos no fim da linha, sem colisao
            for i in range(1, len(ultimos)):
                ultimos[i][0] = max(ultimos[i][0], ultimos[i - 1][0] + 12)
            for yy, txt in ultimos:
                s.append('<text x="%d" y="%.1f" font-size="10.5" fill="%s">%s</text>' % (x0 + PW + 5, yy + 3.5, TEXTO_2, txt))
    s.append('<text x="%.1f" y="%d" font-size="11" text-anchor="middle" fill="%s">β da carga</text>'
             % (L + (3 * PW + 2 * GX) / 2, H - 8, TEXTO_2))
    s.append("</svg>")
    return "\n".join(s)


def mapa_sd(hist_csv, man, aid):
    """Distribuicao da stack distance das cargas completas como mapa de calor: uma linha por
    beta, uma coluna por faixa de distancia, a cor e a fracao dos reusos naquela faixa."""
    rot = {c["sufixo"]: c for c in man["cenarios"]}
    h = {}
    for l in hist_csv:
        if l["amostra"] == "completa":
            h.setdefault(l["cenario"], {})[int(l["faixa_de"])] = float(l["fracao"])
    faixas = sorted({f for v in h.values() for f in v})
    cens = [c["sufixo"] for c in man["cenarios"]]
    CW, CH, L, T = 50, 30, 92, 104
    W, H = L + len(faixas) * CW + 24, T + len(cens) * CH + 74
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SUPERFICIE),
         '<text x="16" y="28" font-size="17" font-weight="600" fill="%s">Distribuição da stack '
         'distance das cargas completas · fase %s</text>' % (TEXTO, aid),
         '<text x="16" y="48" font-size="12" fill="%s">cada célula: fração dos reúsos da carga cuja '
         'stack distance cai naquela faixa · cada linha soma 100%%</text>' % TEXTO_2]
    milhar = lambda v: format(v, ",").replace(",", ".")
    nome_faixa = lambda f: milhar(f)                 # a faixa vai do inicio ate o dobro menos 1
    for j, f in enumerate(faixas):
        x = L + j * CW + CW / 2
        s.append('<text x="%.1f" y="%d" font-size="9.5" text-anchor="middle" fill="%s">%s</text>'
                 % (x, T - 8, TEXTO_3, nome_faixa(f)))
    s.append('<text x="%.1f" y="%d" font-size="11" text-anchor="middle" fill="%s">faixa de stack distance (início da faixa: 0, 1, 2–3, 4–7, … ; a última vai até d_max − 1)</text>'
             % (L + len(faixas) * CW / 2, T - 24, TEXTO_2))
    for i, cen in enumerate(cens):
        y = T + i * CH
        s.append('<text x="%d" y="%.1f" font-size="11.5" text-anchor="end" fill="%s">%s</text>'
                 % (L - 8, y + CH / 2 + 4, TEXTO, rotulo_cenario(rot[cen])))
        for j, f in enumerate(faixas):
            v = h.get(cen, {}).get(f, 0.0)
            x = L + j * CW
            if v <= 0:
                s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="%s"/>'
                         % (x + 1, y + 1, CW - 2, CH - 2, SUPERFICIE, GRADE))
                continue
            k = sum(1 for lim in MAPA_LIMITES if v >= lim)
            s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s"><title>%s · faixa %s: %s%%'
                     '</title></rect>' % (x + 1, y + 1, CW - 2, CH - 2, MAPA_CORES[k],
                                          rotulo_cenario(rot[cen]), nome_faixa(f), num_br(round(100 * v, 1))))
            if v >= 0.01:
                s.append('<text x="%.1f" y="%.1f" font-size="10" text-anchor="middle" fill="%s">%d</text>'
                         % (x + CW / 2, y + CH / 2 + 3.5, "#ffffff" if k >= 3 else TEXTO, round(100 * v)))
    yl = T + len(cens) * CH + 22
    s.append('<text x="%d" y="%d" font-size="11" fill="%s">%% dos reúsos:</text>' % (L, yl + 11, TEXTO_2))
    rot_cl = ["&lt; 2", "2–5", "5–10", "10–20", "20–30", "30–45", "≥ 45"]   # "<" cru invalida o XML
    for k, cor in enumerate(MAPA_CORES):
        x = L + 90 + k * 64
        s.append('<rect x="%d" y="%d" width="14" height="14" rx="2" fill="%s"/>' % (x, yl, cor))
        s.append('<text x="%d" y="%d" font-size="10.5" fill="%s">%s</text>' % (x + 19, yl + 11, TEXTO_2, rot_cl[k]))
    s.append('<text x="%d" y="%d" font-size="10.5" fill="%s">célula vazia: nenhum reúso na faixa; '
             'números: %% arredondado (só acima de 1%%)</text>' % (L, yl + 34, TEXTO_3))
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------- comparacao da stack distance
DIAG = "#9a9994"                                     # diagonal / linha de referencia (neutra)
RAMPA_BETA = ("#63BDB5", "#08595C")                  # a rampa das cargas nos graficos da geracao


def cor_beta(i, n):
    """A mesma rampa turquesa que identifica as cargas nos graficos da geracao (claro = beta alto)."""
    a, b = (tuple(int(c[k:k + 2], 16) for k in (1, 3, 5)) for c in RAMPA_BETA)
    t = i / (n - 1) if n > 1 else 1
    return "#%02X%02X%02X" % tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def escala_sd(dmax, px0, px1):
    """Eixo de stack distance em log(d + 1): cabe o 0, e os rotulos mostram a distancia real."""
    hi = math.log10(dmax + 1)
    f = lambda d: px0 + math.log10(d + 1) / hi * (px1 - px0)
    ticks = [d for d in (0, 1, 10, 100, 1000, 10000, 100000) if d <= dmax]
    return f, ticks


def le_quantis(an, aid):
    q = {}
    for l in le_csv(os.path.join(an, "sd_quantis_%s.csv" % aid)):
        q.setdefault((l["cenario"], l["amostra"]), []).append(int(l["sd"]))
    return q


def qq_facetas(q, tecnicas, cenarios, linhas, colunas, aid):
    """Q-Q: para cada percentil de 1 a 99, x = SD da carga completa e y = SD da amostra."""
    dmax = max(max(v) for v in q.values())
    ex, ticks = escala_sd(dmax, 0, FW)
    ey, _ = escala_sd(dmax, FH, 0)

    def desenha(r, c, x0, y0):
        cen, t = cenarios[c], tecnicas[r]
        orig, amos = q[(cen, "completa")], q[(cen, t)]
        g = []
        for d in ticks:
            g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (x0, y0 + ey(d), x0 + FW, y0 + ey(d), GRADE))
            g.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>' % (x0 + ex(d), y0, x0 + ex(d), y0 + FH, GRADE))
        g.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5" stroke-dasharray="4 3"/>'
                 % (x0, y0 + FH, x0 + FW, y0, DIAG))
        pts = [(x0 + ex(a), y0 + ey(b)) for a, b in zip(orig, amos)]
        g += polilinha(pts, COR_AMOS)
        for i, (px, py) in ((49, pts[49]), (89, pts[89])):       # mediana e p90 marcados
            g.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s" stroke="%s" stroke-width="1.5">'
                     '<title>p%d: completa %s · amostra %s</title></circle>'
                     % (px, py, COR_AMOS if i == 49 else SUPERFICIE, COR_AMOS, i + 1, orig[i], amos[i]))
        return g

    lab = lambda d: num_br(d)
    eixo_x = lambda x0: [(x0 + ex(d), lab(d)) for d in ticks]
    eixo_y = lambda y0: [(y0 + ey(d), lab(d)) for d in ticks]
    itens = [("linha", COR_AMOS, "", "amostra: percentis 1 a 99 (● mediana, ○ p90)"),
             ("linha", DIAG, "4 3", "diagonal: amostra = carga completa")]
    return figura("Q-Q da stack distance · fase %s" % aid,
                  "x: stack distance da carga completa · y: stack distance da amostra, no mesmo percentil (escala log de d + 1)\n"
                  "acima da diagonal: a amostra tem distâncias mais longas; abaixo: mais curtas · só os reúsos (primeiras aparições ficam de fora)",
                  linhas, colunas, desenha, eixo_x, eixo_y, legenda=itens)


def razao_facetas(q, tecnicas, cenarios, linhas, colunas, aid):
    """Razao por percentil: x = percentil, y = (SD da amostra + 1) / (SD da completa + 1), em log."""
    lr = [math.log2((b + 1) / (a + 1)) for (cen, t), v in q.items() if t != "completa"
          for a, b in zip(q[(cen, "completa")], v)]
    lim = max(2, 2 * math.ceil(max(abs(x) for x in lr) / 2))    # simetrico, em potencias de 4
    ey = lambda v: FH / 2 - v / lim * (FH / 2)
    ex = lambda p: (p - 1) / 98 * FW
    yt = list(range(-lim, lim + 1, 2 if lim <= 8 else 4))
    xt = [1, 25, 50, 75, 99]

    def desenha(r, c, x0, y0):
        cen, t = cenarios[c], tecnicas[r]
        orig, amos = q[(cen, "completa")], q[(cen, t)]
        g = []
        for v in yt:
            g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (x0, y0 + ey(v), x0 + FW, y0 + ey(v), GRADE))
        for p in xt:
            g.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>' % (x0 + ex(p), y0, x0 + ex(p), y0 + FH, GRADE))
        g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="1.5"/>'
                 % (x0, y0 + ey(0), x0 + FW, y0 + ey(0), DIAG))
        pts = [(x0 + ex(i + 1), y0 + ey(math.log2((b + 1) / (a + 1)))) for i, (a, b) in enumerate(zip(orig, amos))]
        g += polilinha(pts, COR_AMOS)
        for i in (49, 89):
            g.append('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s" stroke="%s" stroke-width="1.5">'
                     '<title>p%d: razão %s</title></circle>'
                     % (pts[i][0], pts[i][1], COR_AMOS if i == 49 else SUPERFICIE, COR_AMOS, i + 1,
                        num_br(round((amos[i] + 1) / (orig[i] + 1), 2))))
        return g

    fator = lambda v: "1" if v == 0 else ("×%d" % 2 ** v if v > 0 else "÷%d" % 2 ** -v)
    eixo_x = lambda x0: [(x0 + ex(p), "p%d" % p) for p in xt]
    eixo_y = lambda y0: [(y0 + ey(v), fator(v)) for v in yt]
    itens = [("linha", COR_AMOS, "", "razão amostra ÷ carga completa, por percentil (● mediana, ○ p90)"),
             ("linha", DIAG, "", "1 = amostra igual à carga completa")]
    return figura("Razão da stack distance por percentil · fase %s" % aid,
                  "x: percentil dos reúsos (p1 = os mais curtos, p99 = os mais longos) · y: stack distance da amostra ÷ a da carga completa, em log (calculada com d + 1)\n"
                  "acima de 1: a amostra tem distâncias mais longas naquele percentil; abaixo: mais curtas · só os reúsos",
                  linhas, colunas, desenha, eixo_x, eixo_y, legenda=itens)


def percentil_por_tecnica(q, man, tecnicas, aid, pc):
    """Um percentil so: uma faceta por tecnica (grade 3 x 3), um ponto por carga."""
    cens = [c["sufixo"] for c in man["cenarios"]]
    n = len(cens)
    vals = {(cen, t): q[(cen, t)][pc - 1] for cen in cens for t in ["completa"] + tecnicas}
    dmax = max(vals.values())
    PW, PH, GX, GY = 236, 236, 40, 52
    L, T, B, R = 86, 150, 52, 24
    fams = [("sistemática", "sis"), ("janela · take 1k", "t1k"), ("janela · take 10k", "t10k")]
    taxas = [("1%", "p01"), ("10%", "p10"), ("20%", "p20")]
    W = L + 3 * PW + 2 * GX + R
    H = T + 3 * PH + 2 * GY + B
    nome_p = "mediana" if pc == 50 else "percentil %d" % pc
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SUPERFICIE),
         '<text x="16" y="28" font-size="17" font-weight="600" fill="%s">Stack distance: %s da '
         'amostra × da carga completa · fase %s</text>' % (TEXTO, nome_p, aid),
         '<text x="16" y="48" font-size="12" fill="%s">uma faceta por técnica · um ponto por carga · '
         'x: %s da carga completa · y: %s da amostra (escala log de d + 1) · só os reúsos</text>'
         % (TEXTO_2, nome_p, nome_p),
         '<text x="16" y="64" font-size="12" fill="%s">na diagonal ("igual"): a amostra acerta; na linha "×10": a '
         'amostra tem distâncias 10 vezes mais longas; na linha "÷10": 10 vezes mais curtas</text>' % TEXTO_2]
    # legenda das cargas: a mesma rampa dos graficos da geracao
    s.append('<text x="16" y="96" font-size="12" fill="%s">carga:</text>' % TEXTO)
    for i, c in enumerate(man["cenarios"]):
        x = 64 + i * 66
        s.append('<circle cx="%d" cy="92" r="5" fill="%s" stroke="%s" stroke-width="2"/>' % (x, cor_beta(i, n), SUPERFICIE))
        s.append('<text x="%d" y="96" font-size="11" fill="%s">β %s</text>' % (x + 9, TEXTO_2, beta_br(c["beta"])))
    for r, (frot, fsuf) in enumerate(fams):
        for c, (trot, tsuf) in enumerate(taxas):
            t = next(x for x in tecnicas if tsuf in x and (x.startswith("sis") if fsuf == "sis" else x.endswith(fsuf)))
            x0, y0 = L + c * (PW + GX), T + r * (PH + GY)
            ex, ticks = escala_sd(dmax, x0, x0 + PW)
            ey, _ = escala_sd(dmax, y0 + PH, y0)
            s.append('<text x="%.1f" y="%d" font-size="12.5" font-weight="600" text-anchor="middle" fill="%s">'
                     '%s %s</text>' % (x0 + PW / 2, y0 - 10, TEXTO, frot, trot))
            for d in ticks:
                s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (x0, ey(d), x0 + PW, ey(d), GRADE))
                s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>' % (ex(d), y0, ex(d), y0 + PH, GRADE))
                if c == 0:
                    s.append('<text x="%d" y="%.1f" font-size="10" text-anchor="end" fill="%s">%s</text>'
                             % (x0 - 6, ey(d) + 3.5, TEXTO_3, num_br(d)))
                if r == 2:
                    s.append('<text x="%.1f" y="%d" font-size="10" text-anchor="middle" fill="%s">%s</text>'
                             % (ex(d), y0 + PH + 15, TEXTO_3, num_br(d)))
            # x10 e /10: retas paralelas a diagonal, recortadas no painel
            for fat in (10, 0.1):
                xs = [d for d in range(0, int(dmax) + 1, max(1, int(dmax) // 400))]
                pts = [(ex(d), ey((d + 1) * fat - 1)) for d in xs if 0 <= (d + 1) * fat - 1 <= dmax]
                if len(pts) > 1:
                    s.append('<path d="%s" fill="none" stroke="%s" stroke-width="1" stroke-dasharray="2 3"/>'
                             % (" ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", a, b) for i, (a, b) in enumerate(pts)), DIAG))
                    # rotulo no trecho da linha que fica dentro do painel, longe dos cantos
                    lx_, ly_ = pts[int(len(pts) * (0.55 if fat > 1 else 0.6))]
                    s.append('<text x="%.1f" y="%.1f" font-size="10.5" font-weight="600" text-anchor="middle" '
                             'fill="%s" stroke="%s" stroke-width="3.5" paint-order="stroke">%s</text>'
                             % (lx_ + (-12 if fat > 1 else 10), ly_ + (-4 if fat > 1 else 16), TEXTO_2, SUPERFICIE,
                                "×10" if fat > 1 else "÷10"))
            s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5" stroke-dasharray="4 3"/>'
                     % (x0, y0 + PH, x0 + PW, y0, DIAG))
            s.append('<text x="%.1f" y="%.1f" font-size="10.5" font-weight="600" text-anchor="middle" fill="%s" '
                     'stroke="%s" stroke-width="3.5" paint-order="stroke" transform="rotate(-45 %.1f %.1f)">igual</text>'
                     % (x0 + PW * 0.3, y0 + PH * 0.7 - 4, TEXTO_2, SUPERFICIE, x0 + PW * 0.3, y0 + PH * 0.7 - 4))
            s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s"/>' % (x0, y0, PW, PH, EIXO))
            pts = [(ex(vals[(cen, "completa")]), ey(vals[(cen, t)])) for cen in cens]
            s.append('<path d="%s" fill="none" stroke="%s" stroke-width="1"/>'
                     % (" ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", a, b) for i, (a, b) in enumerate(pts)), EIXO))
            for i, (cen, (px, py)) in enumerate(zip(cens, pts)):
                s.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s" stroke="%s" stroke-width="2"><title>%s · %s %s: '
                         'completa %s · amostra %s</title></circle>'
                         % (px, py, cor_beta(i, n), SUPERFICIE, rotulo_cenario(man["cenarios"][i]), frot, trot,
                            num_br(vals[(cen, "completa")]), num_br(vals[(cen, t)])))
    s.append('<text x="%.1f" y="%d" font-size="11" text-anchor="middle" fill="%s">%s da carga completa</text>'
             % (L + (3 * PW + 2 * GX) / 2, H - 10, TEXTO_2, nome_p))
    s.append('<text x="18" y="%.1f" font-size="11" fill="%s" transform="rotate(-90 18 %.1f)" text-anchor="middle">'
             '%s da amostra</text>' % (T + (3 * PH + 2 * GY) / 2, TEXTO_2, T + (3 * PH + 2 * GY) / 2, nome_p))
    s.append("</svg>")
    return "\n".join(s)


# --------------------------------------------------------------- fase
def gera(pasta):
    aid = os.path.basename(pasta).split("-")[0]
    an = os.path.join(pasta, "analise")
    man = json.load(open(os.path.join(pasta, "manifesto.json")))
    cenarios = [c["sufixo"] for c in man["cenarios"]]
    colunas = [rotulo_cenario(c) for c in man["cenarios"]]
    med = le_csv(os.path.join(an, "medidas_%s.csv" % aid))
    tecnicas = []
    for l in med:
        if l["amostra"] != "completa" and l["amostra"] not in tecnicas:
            tecnicas.append(l["amostra"])
    linhas = [rotulo_tecnica(t) for t in tecnicas]
    erro = {(l["cenario"], l["amostra"]): float(l["erro_max_hrc_vs_completa"]) for l in med}

    def por_amostra(nome, cx, cy, cy_orig=None):
        """Agrupa um CSV de curvas em {(cen, tec): (orig, amos)}. Quando o CSV ja traz a original
        numa coluna ao lado (hrc, sd_cdf), cy_orig le dali; senao a original sao as linhas
        'completa' do proprio CSV."""
        pts = {}
        for l in le_csv(os.path.join(an, "%s_%s.csv" % (nome, aid))):
            pts.setdefault((l["cenario"], l["amostra"]), []).append(
                (float(l[cx]), float(l[cy]), float(l[cy_orig]) if cy_orig else None))
        out = {}
        for cen in cenarios:
            for t in tecnicas:
                a = pts[(cen, t)]
                orig = [(x, yo) for x, _, yo in a] if cy_orig else [(x, y) for x, y, _ in pts[(cen, "completa")]]
                out[(cen, t)] = (orig, [(x, y) for x, y, _ in a])
        return out

    def hist(nome, cx, cy):
        h = {}
        for l in le_csv(os.path.join(an, "%s_%s.csv" % (nome, aid))):
            h.setdefault((l["cenario"], l["amostra"]), {})[int(l[cx])] = float(l[cy])
        return {(cen, t): (h[(cen, "completa")], h[(cen, t)]) for cen in cenarios for t in tecnicas}

    specs = [
        ("hrc", "Curva de hit rate (LRU)",
         "y: hit rate · x: tamanho do cache em objetos (log)\n"
         "o mesmo tamanho absoluto de cache na original e na amostra; no canto, o erro máximo da amostra",
         curvas(por_amostra("hrc", "cache_objetos", "hit_amostra", "hit_completa"),
                tecnicas, cenarios, "log", "lin", (0, 1)),
         lambda r, c: "erro máx %s" % ("%.2f" % erro[(cenarios[c], tecnicas[r])]).replace(".", ",")),
        ("sd_cdf", "Acumulada da stack distance",
         "y: fração dos reúsos com SD menor que x · x: stack distance (log)",
         curvas(por_amostra("sd_cdf", "d", "P(d<x)_amostra", "P(d<x)_completa"),
                tecnicas, cenarios, "log", "lin", (0, 1)), None),
        ("sd_histograma", "Histograma da stack distance",
         "y: fração dos reúsos · x: faixa de SD (0, depois oitavas 1, 2–3, 4–7, … ; rótulo = início da faixa)",
         barras(hist("sd_histograma", "faixa_de", "fracao"), tecnicas, cenarios), None),
        ("footprint", "Footprint",
         "y: objetos distintos, média sobre todas as janelas (log) · x: tamanho da janela em requisições (log)",
         curvas(por_amostra("footprint", "janela_requisicoes", "objetos_distintos_media"),
                tecnicas, cenarios, "log", "log"), None),
        ("frequencia", "Frequência por objeto",
         "y: requisições ao objeto (log) · x: rank do objeto, do mais pedido ao menos pedido (log)",
         curvas(por_amostra("frequencia", "rank", "requisicoes_ao_objeto"),
                tecnicas, cenarios, "log", "log"), None),
        ("frequencia_hist", "Histograma de requisições por objeto",
         "y: fração dos objetos · x: requisições ao objeto (oitavas 1, 2–3, 4–7, … ; rótulo = início da faixa)",
         barras(hist("frequencia_hist", "de", "fracao_dos_objetos"), tecnicas, cenarios), None),
    ]
    escritos = []
    for nome, titulo, sub, (desenha, ex, ey), nota in specs:
        svg = figura("%s · fase %s" % (titulo, aid), sub, linhas, colunas, desenha, ex, ey, nota,
                     "barra" if "hist" in nome else "linha")
        arq = os.path.join(an, "%s_%s.svg" % (nome, aid))
        with open(arq, "w") as fh:
            fh.write(svg)
        escritos.append(os.path.basename(arq))
    q = le_quantis(an, aid)
    novos = [("sd_qq", qq_facetas(q, tecnicas, cenarios, linhas, colunas, aid)),
             ("sd_razao", razao_facetas(q, tecnicas, cenarios, linhas, colunas, aid)),
             ("sd_p50", percentil_por_tecnica(q, man, tecnicas, aid, 50)),
             ("sd_p90", percentil_por_tecnica(q, man, tecnicas, aid, 90))]
    primeiras = erro_por_beta(
        med, man, aid, titulo="Primeiras aparições por nível de stack distance",
        subtitulo="y: fração das requisições que são primeira aparição (miss obrigatório; teto do hit rate = "
                  "1 − essa fração) · x: β da carga, da SD mais baixa à mais alta",
        medidas=[("fração de primeiras aparições", "p_inf_medido")], ymax_fixo=1.0, referencia=True)
    for nome, svg in novos + [("primeiras_beta", primeiras), ("erro_beta", erro_por_beta(med, man, aid)),
                      ("sd_mapa", mapa_sd(le_csv(os.path.join(an, "sd_histograma_%s.csv" % aid)), man, aid))]:
        arq = os.path.join(an, "%s_%s.svg" % (nome, aid))
        with open(arq, "w") as fh:
            fh.write(svg)
        escritos.append(os.path.basename(arq))
    return escritos


def main():
    import pipeline
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fase", required=True, help="id (a01) ou nome da pasta da fase")
    a = ap.parse_args()
    pasta = pipeline.acha_fase(a.fase)
    for arq in gera(pasta):
        print("   ", os.path.relpath(os.path.join(pasta, "analise", arq), pipeline.AQUI))


if __name__ == "__main__":
    main()
