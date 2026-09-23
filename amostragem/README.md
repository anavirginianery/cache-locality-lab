# Parte 3 — Amostragem

Ainda não implementada.

Aqui entram os experimentos de estimação da curva por amostragem: **SHARDS** (amostragem
espacial por hash, com as distâncias reescaladas por 1/R) e **simulação em miniatura** (um cache
de tamanho R·C alimentado pela amostra), comparados com a curva exata.

O que torna este laboratório útil para esse estudo: como a distribuição de stack distance das
cargas é conhecida, a curva verdadeira é conhecida também, sem simular. O erro medido num
estimador amostrado é dele — não do desconhecimento da carga.

Perguntas que a parte 3 deve responder:

- Como o erro da estimativa varia com a taxa de amostragem R?
- Como esse erro varia com o **nível de stack distance** da carga? A intuição a testar é que
  cargas de stack distance baixa ficam mal resolvidas quando R é pequeno: se a distância típica
  multiplicada por R for menor que 1, a amostra não consegue distinguir as distâncias curtas.
- Qual o efeito da fração de objetos novos, P(∞), sobre o erro?

O padrão a seguir é o mesmo das outras partes: `experimentos.json` → `pipeline.py` → `resultados/`.

O `lib/genwl.py` já traz o filtro espacial do SHARDS (`analyze --shards R`), que serve de ponto
de partida.
