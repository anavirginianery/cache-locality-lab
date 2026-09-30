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
    for cor, traco, nome in ((COR_ORIG, "", "original (carga completa)"),
                             (COR_AMOS, TRACO_AMOS, "amostrada")):
        if legenda == "barra":                    # o simbolo da legenda e o da marca do grafico
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


# --------------------------------------------------------------- fase
def gera(pasta):
    aid = os.path.basename(pasta).split("-")[0]
    an = os.path.join(pasta, "analise")
    man = json.load(open(os.path.join(pasta, "manifesto.json")))
    cenarios = [c["sufixo"] for c in man["cenarios"]]
    colunas = ["SD %s · β %s" % (c["nome"].replace("media", "média"),
                                 str(c["beta"]).replace(".", ",")) for c in man["cenarios"]]
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
