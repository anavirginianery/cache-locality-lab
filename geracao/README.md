# Geração de carga do experimento

Cargas sintéticas com stack distance controlada, e a conferência de que elas saíram como foram
pedidas. O trabalho é organizado em **fases**: cada fase é uma rodada de experimentação com seus
próprios parâmetros.

```
distribuição de SD   →   carga (trace)   →   conferência
  dist/sd_*.txt          cargas/carga_*.txt    analise/
```

```bash
python3 pipeline.py --fase f01     # roda a fase f01
python3 pipeline.py --fases        # lista as fases já rodadas
```

O resultado principal é o `relatorio_<fase>.html` dentro de `analise/` — abra no navegador.

---

## Fases

Uma fase guarda **o que é comum à rodada**: `dmax`, `inf`, `requisicoes`, `semente`, `caches`.
O que varia entre os cenários daquela fase — hoje o β — aparece no nome dos arquivos.

```
fases/
├── INDEX.md                      # uma linha por fase, gerado automaticamente
└── f01-linha-de-base/
    ├── cenarios.json             # a configuração desta fase — a fonte da verdade
    ├── manifesto.json            # o que foi rodado, quando, em que commit, e como saiu
    ├── dist/                     # sd_f01_baixa-b150.txt
    ├── cargas/                   # carga_f01_baixa-b150.txt
    └── analise/                  # medidas_f01.csv … relatorio_f01.html
```

Cada fase é uma pasta fechada: dá para zipar, comparar com outra, apagar ou mandar para alguém
sem perder o contexto.

### Criar uma fase

```bash
python3 pipeline.py --nova-fase dmax-100k
```

Isso cria `fases/f02-dmax-100k/` com uma cópia do `cenarios.json` da raiz, e para aí. Edite a
configuração da fase e rode:

```bash
python3 pipeline.py --fase f02
```

O id (`f01`, `f02`, …) é sequencial e **nunca muda** — é ele que entra nos nomes dos arquivos.
O apelido fica só no nome da pasta, então você pode renomeá-lo depois sem quebrar nada.

### Proteção contra rodadas misturadas

Se o `cenarios.json` de uma fase mudar depois de ela ter sido rodada, o pipeline recusa:

```
o cenarios.json da fase f01 mudou desde a ultima rodada.
Rode com --refazer para sobrescrever esta fase, ou crie outra com --nova-fase.
```

Isso evita o caso de você ajustar um parâmetro, rodar de novo, e ficar com arquivos de duas
configurações diferentes com o mesmo nome. Para uma rodada maior — 500 mil requisições em vez de
50 mil — o certo é **criar outra fase**, não sobrescrever a existente.

---

## Nomes dos arquivos

| Tipo | Padrão | Exemplo |
|---|---|---|
| Distribuição | `sd_<fase>_<cenário>.txt` | `sd_f01_alta-b050.txt` |
| Carga | `carga_<fase>_<cenário>.txt` | `carga_f01_alta-b050.txt` |
| Análise | `<medida>_<fase>.csv` | `hrc_f01.csv`, `medidas_f01.csv` |
| Gráfico | `<medida>_<fase>.svg` | `footprint_f01.svg` |
| Relatório | `relatorio_<fase>.html` | `relatorio_f01.html` |

O sufixo do cenário lista os parâmetros que variam dentro da fase. Hoje só o β, escrito como
**inteiro de três dígitos multiplicado por 100**, para não ter ponto no meio do nome:

| β | No nome |
|---|---|
| 1,5 | `b150` |
| 1,0 | `b100` |
| 0,5 | `b050` |

Assim os arquivos ordenam por β num `ls`, e o valor de verdade fica no `manifesto.json`.
A regra vale para qualquer parâmetro fracionário que venha a entrar no nome.

---

## O que é stack distance aqui

A **stack distance (SD)** de um reúso é o número de objetos **distintos** requisitados entre
dois pedidos ao mesmo objeto. Se a mesma coisa é pedida duas vezes seguidas, SD = 0.
Num cache LRU de C objetos, um reúso **acerta quando SD < C**.

Por isso, "SD alta" e "SD baixa" só significam alguma coisa **em relação a um tamanho de cache**.
Uma SD de 500 é alta para um cache de 100 objetos e baixa para um de 10.000. O relatório nunca
usa um limiar fixo: ele sempre mostra a fração de reúsos que cabe em **cada** tamanho de cache
configurado na fase.

## As três etapas

**1. Distribuição.** Escreve a lista que diz, para cada valor de SD, qual a chance de ele ser
sorteado. Usa uma lei de potência:

```
P(d) ∝ (d + 1)^(-β)
```

β é a velocidade com que a chance cai conforme a distância cresce.
**β grande → quase todo reúso é curto (SD baixa). β pequeno → muitos reúsos longos (SD alta).**
Além de β, entram `dmax` (maior distância possível) e `inf` (fração das requisições que são
objetos novos, que nunca podem ser acerto).

**2. Carga.** O LRU Stack Model lê essa lista e gera o trace: a cada requisição sorteia uma
distância d e requisita o objeto que está nessa profundidade da pilha LRU. Uma linha por
requisição, contendo o id do objeto.

O trace começa com um **prefixo de aquecimento** (uma linha por objeto da pilha inicial,
`dmax` linhas). Sem ele, os objetos da pilha inicial apareceriam como "objeto novo" na primeira
vez. Nas medidas, esse prefixo é descartado — e, se você usar o trace em outro simulador,
descarte também as `dmax` primeiras linhas das estatísticas.

**3. Conferência.** Mede a carga gerada e compara com o valor teórico, que sai direto da
distribuição, sem simular:

```
hit(C) = (1 − P(∞)) · P(d < C)
```

Em palavras: acerta quem é reúso e cuja stack distance cabe no cache. Se o medido e o teórico
batem, a carga tem a stack distance que foi pedida. (O miss ratio é o complemento, 1 − hit; as
análises usam a curva de hit rate.)

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `cenarios.json` (raiz) | O modelo, copiado para dentro de cada fase nova. |
| `pipeline.py` | Roda as três etapas de uma fase. |
| `modelo_relatorio.html` | Modelo do relatório; o pipeline preenche. Não precisa mexer. |
| `fases/INDEX.md` | Uma linha por fase: parâmetros, data e se conferiu. |
| `fases/<fase>/cenarios.json` | A configuração daquela fase. É o que você edita. |
| `fases/<fase>/manifesto.json` | Parâmetros usados, commit do código, arquivos gerados e resumo dos resultados. |
| `.../dist/sd_*.txt` | A distribuição de SD: linhas `d prob`, `a-b prob` e `inf prob`. |
| `.../cargas/carga_*.txt` | O trace: um id de objeto por linha. |
| `.../analise/medidas_*.csv` | Uma linha por cenário: percentis da SD, footprint, objetos distintos, erro. |
| `.../analise/hrc_*.csv` | Curva de hit rate, teórica e medida, ponto a ponto. |
| `.../analise/sd_cdf_*.csv` | Acumulada da SD, teórica e medida. |
| `.../analise/sd_histograma_*.csv` | Quantos reúsos em cada faixa de SD (faixas dobrando: 1, 2, 4, 8, …). |
| `.../analise/footprint_*.csv` | Footprint: objetos distintos por janela de N requisições, em média. |
| `.../analise/conferencia_*.csv` | Hit teórico × medido em cada tamanho de cache, e a fração de reúsos que cabem (e que não cabem) nele. |
| `.../analise/*.svg` | Os quatro gráficos soltos, prontos para entrar em um documento. |
| `.../analise/relatorio_*.html` | Tudo junto, para leitura. |

## Configuração de uma fase

| Campo | O que faz |
|---|---|
| `descricao` | Uma frase sobre o objetivo da fase. Aparece no relatório e no manifesto. |
| `dmax` | Maior stack distance possível. Define a escala: nenhum reúso passa disso. |
| `inf` | Fração das requisições que são objetos novos. Igual em todos os cenários da fase, para não misturar novidade com localidade. |
| `requisicoes` | Tamanho da carga, sem contar o aquecimento. |
| `semente` | Fixa o sorteio: a mesma semente gera exatamente a mesma carga. |
| `caches` | Tamanhos de cache usados na conferência e no relatório. Coloque aqui os tamanhos do seu experimento. |
| `tolerancia` | Erro máximo aceito entre hit medido e teórico para o cenário ser marcado como "confere". |
| `cenarios[]` | `nome` (entra no nome dos arquivos), `beta` e `rotulo` (o nome que aparece no relatório). |

Para acrescentar um cenário, basta mais uma entrada na lista:

```json
{"nome": "muito_alta", "beta": 0.3, "rotulo": "SD muito alta"}
```

Rodar de novo só a análise, sem regerar distribuições nem cargas (útil ao mexer em gráficos ou
tabelas):

```bash
python3 pipeline.py --fase f01 --so-analise
```

## Como ler os resultados

- **SD mediana** — metade dos reúsos teve distância menor que esse valor. É o resumo mais direto
  do nível de stack distance da carga.
- **SD p90** — 90% dos reúsos ficaram abaixo desse valor. Mostra o alcance da cauda.
- **Reúsos que cabem** — a fração que aquele tamanho de cache consegue atender. A fração
  complementar, dos que não cabem, é o número para dizer "esta carga tem stack distance alta
  **para um cache de C objetos**".
- **Erro** — hit medido menos hit teórico. Perto de zero significa que a carga reproduz a
  distribuição pedida; é a conferência do gerador, não um resultado do experimento. Com 50 mil
  requisições fica na casa de 0,005; com 500 mil, cai para 0,001.
- **Objetos distintos** — quantos objetos diferentes apareceram. Não é um parâmetro: emerge do
  nível de stack distance (quanto maior a SD, mais objetos ficam ativos).
- **Footprint** — quantos objetos distintos aparecem numa janela de N requisições. Também emerge
  da stack distance: a SD de um reúso é, por definição, a contagem de objetos distintos na janela
  entre dois pedidos ao mesmo objeto.

## As ferramentas

O pipeline usa os dois scripts de `lib/`, que também funcionam sozinhos na linha de comando:

```bash
# 1. distribuição
python3 ../lib/mkps.py potencia --beta 1.0 --dmax 10000 --inf 0.05 -o sd.txt

# 2. carga
python3 ../lib/genwl.py gen --model lrusm --sd-file sd.txt --emit-warmup \
        --requests 50000 --seed 7 -o carga.txt

# 3. conferência rápida
python3 ../lib/genwl.py analyze carga.txt --skip 10000 --sizes 10,100,1000
```

O `mkps.py` tem outros construtores de distribuição além da lei de potência (`faixas`, `irm`,
`mistura`, `mrc`, `trace`, `transformar`); rode `python3 ../lib/mkps.py --help` para ver. O
pipeline usa a lei de potência porque ela tem um botão só.
