# Parte 2 — Simulação

Ainda não implementada.

Aqui entram os simuladores de política de despejo aplicados às cargas geradas em `geracao/`:
LRU como linha de base (que tem resultado teórico conhecido, vindo da distribuição de stack
distance) e as demais políticas por simulação — FIFO, LFU, ARC, LIRS, 2Q, SIEVE, S3-FIFO.

O padrão a seguir é o mesmo da geração:

```
experimentos.json   →   pipeline.py   →   resultados/
```

- **`experimentos.json`** — quais cargas, quais políticas, quais tamanhos de cache.
- **`pipeline.py`** — roda as simulações e escreve CSVs, SVGs e um relatório em HTML.
- **Conferência** — para LRU, o resultado simulado deve bater com o teórico da distribuição.
  É a mesma ideia da parte 1: uma âncora conhecida para validar o instrumento antes de confiar
  nos números das outras políticas.

Uma observação registrada em `METODOLOGIA.md`, seção 9: as cargas geradas pelo LRU Stack Model
têm popularidade passageira, o que desfavorece políticas guiadas por frequência. Comparações
envolvendo LFU e parentes precisam desse contexto.
