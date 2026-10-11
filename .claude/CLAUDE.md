# Modelos de decisão

Bateria de casos de uso, para avaliar modelos de decisão do tipo *System One* (`POST /v1/systemone`).
Esses modelos não geram texto: recebem um **state** e perguntas tipadas (`choice`, `score`, `noul`) e devolvem
probabilidades. A decisão final fica no código.

- **Jev** (TypeSafe): modelo hospedado (`jev-1.13.0`).
- **Laya**: alternativa open source com a mesma API, rodando local em Docker.

Cada caso de uso tem cenários normais e cenários bônus ("teste de fogo"), pensados para levar o modelo ao limite.

## Como executar

```bash
./run-laya-server.sh                           # sobe o Laya em Docker (só para --provider laya)
uv run python main.py                          # 12 exemplos + cenários bônus + report HTML
uv run python main.py --only 3 triagem-emails  # só alguns exemplos (número ou slug)
uv run python main.py --provider jev           # sobrescreve MODEL_PROVIDER do .env
uv run python main.py --no-bonus --no-report   # sem teste de fogo, só o trace JSON
uv run python main.py --report-from output/run_laya_<data>.json  # só regera o HTML
```

Cada execução salva em `output/` o trace completo (`run_<provider>_<data>.json`) e o report (`.html`).

## Estrutura

- `examples/`: um arquivo por caso de uso; recebe o `ModelDecision` da factory por injeção de dependência.
- `modelDecision/`: factory e integrações com Jev e Laya.
- `execution/results.py`: modelo neutro de resultados/trace, produzido pelos exemplos e consumido pelo report.
- `report/html_report.py`: gera o HTML a partir de um `RunResult`, sem executar exemplos.
- `docs/`: avaliações detalhadas (ver abaixo).