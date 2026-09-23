# Geração de carga do experimento

Esta pasta contém a parte de **geração de carga**: cargas sintéticas com stack distance
controlada, e a conferência de que elas saíram como foram pedidas.

```
distribuição de SD   →   carga (trace)   →   conferência
  dist/sd_*.txt          cargas/carga_*.txt    analise/*.csv, *.svg, relatorio.html
```

Rodar tudo:

```bash
python3 pipeline.py
```

O resultado principal é `analise/relatorio.html` — abra no navegador.

---

## O que é stack distance aqui

A **stack distance (SD)** de um reúso é o número de objetos **distintos** requisitados entre
dois pedidos ao mesmo objeto. Se a mesma coisa é pedida duas vezes seguidas, SD = 0.
Num cache LRU de C objetos, um reúso **acerta quando SD < C**.

Por isso, "SD alta" e "SD baixa" só significam alguma coisa **em relação a um tamanho de cache**.
Uma SD de 500 é alta para um cache de 100 objetos e baixa para um de 10.000. O relatório nunca
usa um limiar fixo: ele sempre mostra a fração de reúsos com SD maior ou igual a **cada** tamanho
de cache configurado em `cenarios.json`.

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

## Arquivos

| Arquivo | O que é |
|---|---|
| `cenarios.json` | A configuração. É o único arquivo que você edita no dia a dia. |
| `pipeline.py` | Roda as três etapas para cada cenário. |
| `modelo_relatorio.html` | Modelo do relatório; o pipeline preenche. Não precisa mexer. |
| `dist/sd_<cenario>.txt` | A distribuição de SD: linhas `d prob`, `a-b prob` e `inf prob`. |
| `cargas/carga_<cenario>.txt` | O trace: um id de objeto por linha. |
| `analise/medidas.csv` | Uma linha por cenário: percentis da SD, objetos distintos, erro, confere sim/não. |
| `analise/hrc.csv` | Curva de hit rate, teórica e medida, ponto a ponto. |
| `analise/sd_cdf.csv` | Acumulada da SD, teórica e medida. |
| `analise/sd_histograma.csv` | Quantos reúsos em cada faixa de SD (faixas dobrando: 1, 2, 4, 8, …). |
| `analise/footprint.csv` | Footprint: objetos distintos por janela de N requisições, em média. |
| `analise/conferencia.csv` | Hit teórico × medido em cada tamanho de cache, e a fração de reúsos que cabem (e que não cabem) nele. |
| `analise/*.svg` | Os quatro gráficos soltos, prontos para entrar em um documento. |
| `analise/relatorio.html` | Tudo junto, para leitura. |

## Configuração (`cenarios.json`)

| Campo | O que faz |
|---|---|
| `dmax` | Maior stack distance possível. Define a escala: nenhum reúso passa disso. |
| `inf` | Fração das requisições que são objetos novos. Igual em todos os cenários, para não misturar novidade com localidade. |
| `requisicoes` | Tamanho da carga, sem contar o aquecimento. |
| `semente` | Fixa o sorteio: a mesma semente gera exatamente a mesma carga. |
| `caches` | Tamanhos de cache usados na conferência e no relatório. Coloque aqui os tamanhos do seu experimento. |
| `tolerancia` | Erro máximo aceito entre hit medido e teórico para o cenário ser marcado como "confere". |
| `cenarios[]` | `nome` (usado nos arquivos), `beta` e `rotulo` (o nome que aparece no relatório). |

Para acrescentar um cenário, basta mais uma entrada na lista:

```json
{"nome": "muito_alta", "beta": 0.3, "rotulo": "SD muito alta"}
```

## Cargas maiores

A configuração padrão usa 50.000 requisições, que roda em segundos e serve para validar.
Para o experimento de verdade:

```bash
python3 pipeline.py --requisicoes 500000
```

Cargas maiores diminuem o ruído: com 50.000 requisições o erro entre medido e teórico fica na
casa de 0,005; com 500.000, cai para 0,001. A rodada com 500.000 requisições nos três cenários
leva cerca de 17 segundos.

Só refazer a análise, sem regerar as cargas (útil ao mexer em gráficos ou tabelas):

```bash
python3 pipeline.py --so-analise
```

## Como ler os resultados

- **SD mediana** — metade dos reúsos teve distância menor que esse valor. É o resumo mais direto
  do nível de stack distance da carga.
- **SD p90** — 90% dos reúsos ficaram abaixo desse valor. Mostra o alcance da cauda.
- **Reúsos com SD ≥ cache** — a fração que aquele tamanho de cache não consegue atender.
  É o número para dizer "esta carga tem stack distance alta **para um cache de C objetos**".
- **Erro** — hit medido menos hit teórico. Perto de zero significa que a carga reproduz a
  distribuição pedida; é a conferência do gerador, não um resultado do experimento.
- **Objetos distintos** — quantos objetos diferentes apareceram. Não é um parâmetro: emerge do
  nível de stack distance (quanto maior a SD, mais objetos ficam ativos).
- **Footprint** — quantos objetos distintos aparecem numa janela de N requisições. Também emerge
  da stack distance: a SD de um reúso é, por definição, a contagem de objetos distintos na janela
  entre dois pedidos ao mesmo objeto. Ver `analise/footprint.csv`.

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
`mistura`, `mrc`, `trace`, `transformar`); rode `python3 ../lib/mkps.py --help` para ver. O pipeline
usa a lei de potência porque ela tem um botão só.
