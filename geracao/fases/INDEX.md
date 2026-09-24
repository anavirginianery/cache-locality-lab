# Fases de experimentacao

Gerado por `pipeline.py`. Cada fase e uma rodada com parametros comuns proprios;
os detalhes de cada uma estao no `manifesto.json` dentro da pasta.

| Fase | Apelido | Data | dmax | inf | Requisicoes | Semente | Betas | Erro max | Confere |
|---|---|---|---|---|---|---|---|---|---|
| [f01](f01-linha-de-base/) | linha-de-base | 2026-09-23 | 10.000 | 0,05 | 50.000 | 7 | 1,5 / 1,0 / 0,5 | 0,0068 | sim |
| [f02](f02-500k/) | 500k | 2026-09-23 | 10.000 | 0,05 | 500.000 | 7 | 1,5 / 1,0 / 0,5 | 0,001 | sim |
| [f03](f03-experimento/) | experimento | 2026-09-24 | 10.000 | 0,05 | 1.000.000 | 7 | 1,5 / 1,0 / 0,5 | 0,0008 | sim |
