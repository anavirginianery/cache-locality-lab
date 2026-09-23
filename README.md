# cache-locality-lab

Laboratório para estudar o comportamento de caches em função da **localidade** das cargas de
trabalho — geração de cargas sintéticas com stack distance controlada, simulação de políticas
e experimentos de amostragem.

O fio condutor é a **stack distance**: o número de objetos distintos requisitados entre dois
pedidos ao mesmo objeto. Num cache LRU de C objetos, um reúso acerta exatamente quando a stack
distance é menor que C, e daí:

```
hit(C) = (1 − P(∞)) · P(d < C)
```

Isso torna a distribuição de stack distance uma variável de experimento: fixando-a, a curva de
hit rate é conhecida antes de qualquer simulação, e serve de gabarito para conferir tudo o mais.

A fundamentação, as decisões de modelagem e os resultados estão em **[`METODOLOGIA.md`](METODOLOGIA.md)**,
que é um documento vivo e cresce junto com o experimento.

## As três partes

| Parte | Pasta | Estado |
|---|---|---|
| **Geração** — cargas sintéticas com stack distance controlada | [`geracao/`](geracao/) | pronta |
| **Simulação** — políticas de despejo sobre as cargas geradas | [`simulacao/`](simulacao/) | a fazer |
| **Amostragem** — SHARDS e simulação em miniatura | [`amostragem/`](amostragem/) | a fazer |

Cada parte segue o mesmo padrão: um arquivo de configuração em JSON, um `pipeline.py` que roda
de ponta a ponta, e uma pasta de saída com CSVs, gráficos em SVG e um relatório em HTML.

## Rodando a geração

```bash
cd geracao
python3 pipeline.py                       # 50.000 requisições por cenário (validação, segundos)
python3 pipeline.py --requisicoes 500000  # tamanho do experimento
```

O resultado principal é `geracao/analise/relatorio.html`. Não há dependências além do Python 3 —
nem numpy, nem pacote nenhum.

O pipeline roda três etapas encadeadas:

```
distribuição de SD   →   carga (trace)   →   conferência
  dist/sd_*.txt          cargas/carga_*.txt    analise/
```

A conferência compara cada medida da carga gerada com o valor teórico calculado diretamente da
distribuição. Nos três cenários atuais, o erro máximo entre hit rate medido e teórico é de 0,006
com 50 mil requisições e 0,001 com 500 mil.

## Estrutura

```
.
├── METODOLOGIA.md        documento vivo: fundamentação, decisões e resultados
├── lib/
│   ├── genwl.py          gerador de carga (LRU Stack Model) e medidas de stack distance
│   └── mkps.py           construtor da distribuição de stack distance
├── geracao/              parte 1 — ver geracao/README.md
│   ├── cenarios.json     a configuração dos cenários
│   ├── pipeline.py
│   ├── dist/             as distribuições de SD (versionadas)
│   ├── cargas/           os traces (fora do versionamento: grandes e reprodutíveis)
│   └── analise/          CSVs, SVGs e o relatório
├── simulacao/            parte 2
├── amostragem/           parte 3
└── docs/                 material de estudo
    ├── controlando-stack-distance.html   panorama de geradores de carga e da literatura
    ├── tragen-por-dentro.html            o TRAGEN peça por peça, e a abordagem usada aqui
    └── tragen_mini.py                    reimplementação didática do núcleo do TRAGEN
```

Os traces não são versionados porque a semente está fixa em `cenarios.json`: a mesma configuração
gera exatamente as mesmas cargas. O que entra no repositório são as distribuições e as análises.

## As ferramentas de `lib/`

Funcionam sozinhas na linha de comando, fora do pipeline:

```bash
# construir uma distribuição de stack distance
python3 lib/mkps.py potencia --beta 1.0 --dmax 10000 --inf 0.05 -o sd.txt

# gerar uma carga a partir dela
python3 lib/genwl.py gen --model lrusm --sd-file sd.txt --emit-warmup \
        --requests 50000 --seed 7 -o carga.txt

# medir a carga
python3 lib/genwl.py analyze carga.txt --skip 10000 --sizes 10,100,1000
```

O `mkps.py` oferece seis construtores de distribuição — `potencia`, `faixas`, `irm`, `mistura`,
`mrc` e `trace` —, além do operador `transformar`. O pipeline usa a lei de potência, que tem um
parâmetro só: **β**, a velocidade com que a probabilidade cai conforme a distância cresce.
β alto concentra os reúsos em distâncias curtas (stack distance baixa); β baixo espalha para
distâncias longas (stack distance alta).

## Referências principais

- Mattson et al. *Evaluation techniques for storage hierarchies.* IBM Systems Journal, 1970.
- Turner, Strecker. *Use of the LRU stack depth distribution for simulation of paging behavior.* CACM, 1977.
- Sundarrajan et al. *Footprint descriptors: theory and practice of cache provisioning in a global CDN.* CoNEXT, 2017.
- Sabnis, Sitaraman. *TRAGEN: a synthetic trace generator for realistic cache simulations.* IMC, 2021.
- Waldspurger et al. *Efficient MRC construction with SHARDS.* FAST, 2015.

A lista completa está em [`METODOLOGIA.md`](METODOLOGIA.md).
