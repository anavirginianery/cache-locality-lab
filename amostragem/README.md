# Parte 3 — Amostragem

Os métodos avaliados são os do `cache-sampling`: **amostragem sistemática** e **amostragem por
janela**, a 1, 10 e 20%. Eles rodam aqui sobre as cargas sintéticas de `geracao/`, com os scripts
originais sem modificação. Como a distribuição de stack distance das cargas é controlada, dá para
ver como o erro de cada método muda com o nível de localidade da carga.

```
cargas da geração  →  1. conversão  →  2. amostragem         →  3. resumo        →  4. análise
carga_f03_*.txt       entrada/*.csv    amostras/*.csv           amostras_a01.csv    medidas_a01.csv, hrc_a01.csv ...
(um id por linha)     (ts,id,1)        (scripts do cache-sampling)
```

A etapa 4 usa o **mesmo instrumento de medida da geração** (`lib/medidas.py`): stack distance,
curva de hit rate LRU, footprint e frequência por objeto, aplicados à carga completa e a cada
amostra.

```bash
python3 pipeline.py --nova-fase temporal-f03   # cria fases/a01-temporal-f03/ e para
python3 pipeline.py --fase a01                 # roda
python3 pipeline.py --fase a01 --so-analise    # não reamostra, só remede
python3 pipeline.py --fases                    # lista as fases já rodadas
```

## Fases

O padrão é o da geração, com ids `a01`, `a02`, … para não se confundirem com as fases `f` de
origem. Cada fase lê as cargas de **uma** fase da geração, indicada no campo `origem`.

```
fases/
├── INDEX.md
└── a01-temporal-f03/
    ├── experimentos.json   a configuração (fonte da verdade)
    ├── manifesto.json      origem, hash das cargas e dos scripts, e o resumo de cada amostra
    ├── LEIAME.md           o que é cada arquivo, nome a nome (gerado)
    ├── entrada/            trace_a01_baixa-b150.csv
    ├── amostras/           amostra_a01_baixa-b150_jan-p10-t1k.csv
    └── analise/            amostras_a01.csv, medidas_a01.csv, hrc_a01.csv ...
```

O manifesto guarda o hash de cada carga de origem. Se a fase `f03` for regerada, ou se o
`experimentos.json` mudar, o pipeline recusa rodar por cima: é preciso `--refazer` ou uma fase nova.
`entrada/` e `amostras/` ficam fora do versionamento, porque se reproduzem a partir das cargas.

| Campo | O que faz |
|---|---|
| `origem` | Fase da geração cujas cargas são amostradas (`f03`). |
| `aquecimento` | `descartar` (padrão) tira as `dmax` primeiras linhas de cada carga antes de amostrar; `manter` amostra o arquivo inteiro. |
| `scripts` | Pasta dos scripts do cache-sampling, relativa à raiz do laboratório. |
| `metodos` | Qualquer subconjunto de `sistematica`, `janela-1k`, `janela-10k`. As taxas (1, 10, 20%) e as janelas vêm fixas dos scripts. |

## Nomes dos arquivos

`amostra_<fase>_<cenário>_<método>.csv`

| Trecho do método | Significado | Tipo no cache-sampling |
|---|---|---|
| `sis-p01`, `sis-p10`, `sis-p20` | sistemática: uma linha a cada 100, 10 ou 5 | `systematic_one/ten/twenty` |
| `jan-p01-t1k` … `jan-p20-t1k` | janela: as últimas 1.000 linhas de cada janela de 100 mil, 10 mil ou 5 mil | `window_one/ten/twenty_1k` |
| `jan-p01-t10k` … `jan-p20-t10k` | janela: as últimas 10.000 linhas de cada janela de 1 milhão, 100 mil ou 50 mil | `window_one/ten/twenty_10k` |

A taxa entra em pontos percentuais com dois dígitos (`p01`, `p10`, `p20`), para ordenar num `ls`.
A coluna da direita é o nome que o mesmo tipo de amostra tem no `results.csv` do cache-sampling.

## Formato: o que foi adaptado

As cargas daqui e os traces do cache-sampling têm formatos diferentes. A conversão resolve assim:

| | Carga da geração | Esperado pelo cache-sampling | Conversão |
|---|---|---|---|
| Colunas | só o id do objeto | `timestamp,id,tamanho` | `posição,id,1` |
| Cabeçalho | não | não (o simulador não pula cabeçalho) | não |
| Aquecimento | `dmax` linhas iniciais | não existe | descartadas (configurável) |
| Timestamp | não existe | usado só pelo TTL | posição na carga; com TTL infinito não afeta nada |
| Tamanho | não existe | ignorado pelo simulador (conta objetos) | 1 |

Conferido: o `cache-simulator` do cache-sampling, rodado sobre `entrada/trace_a01_*.csv`, dá o hit
rate teórico da `f03` (C = 100, SD baixa: 0,8843 simulado contra 0,8842 teórico).

## A análise (etapa 4)

Cada cenário é medido três vezes com a mesma régua: a **teoria** (curva LRU calculada da
distribuição da fase de origem), a **carga completa** (`entrada/`) e **cada amostra**. Todo CSV
tem as colunas `cenario` e `amostra`, e a carga completa aparece como `amostra = completa`.

Tudo é medido como o simulador veria o arquivo: cache vazio no começo, nenhuma linha descartada.
A curva de hit usa os **mesmos tamanhos absolutos de cache** na amostra e na completa, como faz o
`cache-sampling`, e o erro de cada amostra é contra a completa. Conferido: o `cache-simulator` sobre
as amostras dá o mesmo hit rate que `hrc_a01.csv` (por exemplo 0,1293 para `sis-p10`, SD média,
C = 100).

| Arquivo | O que é |
|---|---|
| `amostras_<fase>.csv` | Inventário: linhas, fração real, objetos distintos, blocos contínuos, tipo no cache-sampling. |
| `medidas_<fase>.csv` | Uma linha por amostra: percentis da SD, objetos distintos, footprint em 1.000 req, frequência; erro da curva de hit contra a completa: máximo, tamanho de cache em que ocorre e médio absoluto. |
| `hrc_<fase>.csv` | Curva de hit: teórica, completa, amostra e erro (amostra − completa), ponto a ponto. |
| `sd_cdf_<fase>.csv` | Acumulada da SD, completa e amostra. |
| `sd_histograma_<fase>.csv` | Reúsos por faixa de SD (d = 0, depois oitavas). |
| `footprint_<fase>.csv` | Objetos distintos por janela de N requisições. |
| `frequencia_<fase>.csv` / `frequencia_hist_<fase>.csv` | Curva rank × pedidos e histograma de pedidos por objeto. |

**Gráficos.** Um SVG por métrica, em `analise/` com o mesmo nome do CSV (`hrc_a01.svg`,
`sd_cdf_a01.svg`, `sd_histograma_a01.svg`, `footprint_a01.svg`, `frequencia_a01.svg`,
`frequencia_hist_a01.svg`). Cada figura é uma grade de facetas: **uma linha por técnica de
amostragem, uma coluna por nível de SD**, e em cada faceta a original (azul, contínua) contra a
amostrada (laranja, tracejada). Os eixos são os mesmos em todas as facetas de uma figura, então dá
para comparar tanto entre técnicas quanto entre níveis de SD. No gráfico de hit, cada faceta traz
o erro máximo da amostra. Saem no fim do pipeline, ou sozinhos com `python3 graficos.py --fase a01`.

A carga completa sem o aquecimento começa com o cache vazio, então a SD dela difere um pouco da
medida na geração (mediana 72 contra 74 na SD média). É a mesma referência que o cache-sampling usa
(o fulltrace simulado do zero); a teoria continua ao lado para quem quiser o gabarito exato.

## Cuidados ao ler os resultados

- **A sistemática tem uma linha a mais** (10.001 em vez de 10.000). O `systematic_sampling.sh`
  foi escrito supondo que a primeira linha do arquivo é um cabeçalho com os nomes das colunas, e a
  copia para as três amostras antes de começar a contar (`NR == 1 { print ...; next }`). Só que o
  trace não tem cabeçalho, nem aqui nem no cache-sampling original: a linha 1 é uma requisição de
  verdade. Então cada amostra sistemática leva a requisição 1 **mais** as requisições 100, 200,
  300, … (a 1%). Acontece igual nos traces do Twitter; não foi corrigido para manter o método
  idêntico, e o efeito é uma requisição a mais em 10 mil.
- **As janelas foram dimensionadas para traces de centenas de milhões de linhas.** Numa carga de
  1 milhão, `jan-p01-t10k` é **um único trecho contínuo** de 10 mil requisições, e `jan-p01-t1k`
  são 10 trechos. A coluna `blocos` de `amostras_<fase>.csv` mostra isso para cada amostra.
- **Nenhum dos dois métodos preserva a stack distance.** Na sistemática, um reúso só sobrevive se
  os dois pedidos caírem na amostra; na janela, os reúsos que atravessam trechos são cortados e
  cada trecho recomeça quase frio. A curva da amostra não é uma versão reescalada da original, e
  é justamente essa distorção que a análise mede.
