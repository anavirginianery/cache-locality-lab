# Fase a02 de amostragem

Amostragem temporal (sistematica e por janela) das onze cargas da fase f04

Gerado por `amostragem/pipeline.py`; nao edite a mao.

- **Origem:** fase `f04` da geracao (`f04-onze-betas`)
- **Aquecimento:** descartar as primeiras `dmax` linhas de cada carga antes de amostrar
- **Scripts:** `../cache-sampling/sampling` (sem modificacao)

## Como ler os nomes

`amostra_<fase>_<cenario>_<metodo>.csv`, por exemplo `amostra_a02_baixa-b150_jan-p10-t1k.csv`:

| Trecho | Significado |
|---|---|
| `a02` | esta fase de amostragem (a origem esta no manifesto) |
| `baixa-b150` | cenario da carga de origem: nivel de SD e beta x100 (1,5) |
| `sis-p10` | amostragem **sistematica**, 10%: uma linha a cada 10 |
| `jan-p10-t1k` | amostragem por **janela**, 10%: as ultimas 1.000 linhas de cada janela de 10.000 |

Todo arquivo de `entrada/` e `amostras/` tem uma linha por requisicao, `ts,id,tamanho`, sem cabecalho. O `ts` e a posicao da requisicao na carga (sem o aquecimento, se ele foi descartado), entao numa amostra ele mostra de onde cada linha veio. O tamanho e sempre 1.

## Arquivos

| Arquivo | Metodo | Taxa | Janela | Take | Tipo no cache-sampling | Linhas | Blocos |
|---|---|---|---|---|---|---|---|
| `amostra_a02_sd01-b300_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd01-b300_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd01-b300_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd01-b300_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd01-b300_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd01-b300_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd01-b300_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd01-b300_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd01-b300_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd02-b250_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd02-b250_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd02-b250_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd02-b250_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd02-b250_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd02-b250_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd02-b250_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd02-b250_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd02-b250_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd03-b200_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd03-b200_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd03-b200_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd03-b200_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd03-b200_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd03-b200_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd03-b200_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd03-b200_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd03-b200_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd04-b175_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd04-b175_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd04-b175_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd04-b175_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd04-b175_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd04-b175_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd04-b175_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd04-b175_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd04-b175_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd05-b150_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd05-b150_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd05-b150_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd05-b150_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd05-b150_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd05-b150_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd05-b150_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd05-b150_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd05-b150_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd06-b125_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd06-b125_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd06-b125_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd06-b125_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd06-b125_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd06-b125_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd06-b125_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd06-b125_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd06-b125_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd07-b100_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd07-b100_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd07-b100_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd07-b100_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd07-b100_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd07-b100_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd07-b100_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd07-b100_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd07-b100_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd08-b075_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd08-b075_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd08-b075_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd08-b075_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd08-b075_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd08-b075_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd08-b075_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd08-b075_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd08-b075_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd09-b050_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd09-b050_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd09-b050_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd09-b050_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd09-b050_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd09-b050_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd09-b050_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd09-b050_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd09-b050_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd10-b025_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd10-b025_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd10-b025_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd10-b025_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd10-b025_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd10-b025_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd10-b025_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd10-b025_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd10-b025_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |
| `amostra_a02_sd11-b000_sis-p01.csv` | sistematica | 1% | - | - | `systematic_one` | 10.001 | 10001 |
| `amostra_a02_sd11-b000_sis-p10.csv` | sistematica | 10% | - | - | `systematic_ten` | 100.001 | 100001 |
| `amostra_a02_sd11-b000_sis-p20.csv` | sistematica | 20% | - | - | `systematic_twenty` | 200.001 | 200001 |
| `amostra_a02_sd11-b000_jan-p01-t1k.csv` | janela-1k | 1% | 100000 | 1000 | `window_one_1k` | 10.000 | 10 |
| `amostra_a02_sd11-b000_jan-p10-t1k.csv` | janela-1k | 10% | 10000 | 1000 | `window_ten_1k` | 100.000 | 100 |
| `amostra_a02_sd11-b000_jan-p20-t1k.csv` | janela-1k | 20% | 5000 | 1000 | `window_twenty_1k` | 200.000 | 200 |
| `amostra_a02_sd11-b000_jan-p01-t10k.csv` | janela-10k | 1% | 1000000 | 10000 | `window_one_10k` | 10.000 | 1 |
| `amostra_a02_sd11-b000_jan-p10-t10k.csv` | janela-10k | 10% | 100000 | 10000 | `window_ten_10k` | 100.000 | 10 |
| `amostra_a02_sd11-b000_jan-p20-t10k.csv` | janela-10k | 20% | 50000 | 10000 | `window_twenty_10k` | 200.000 | 20 |

Em `analise/`: `amostras_a02.csv` e o inventario acima, completo; os demais CSVs sao as medidas da geracao (stack distance, curva de hit, footprint, frequencia) aplicadas a carga completa (`amostra = completa`) e a cada amostra. Ver `amostragem/README.md`.
