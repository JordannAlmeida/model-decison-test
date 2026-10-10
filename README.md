# To run docker laya server

execute script `run-laya-server.sh`

# Exemplos de uso do modelo de decisão

```bash
uv run python main.py                          # 12 exemplos + cenários bônus + report HTML
uv run python main.py --only 3 triagem-emails  # só alguns exemplos (número ou slug)
uv run python main.py --provider jev           # sobrescreve MODEL_PROVIDER do .env
uv run python main.py --no-bonus --no-report   # sem teste de fogo, só o trace JSON
uv run python main.py --report-from output/run_laya_<data>.json  # só regera o HTML
```

Cada execução salva em `output/` o trace completo (`run_<provider>_<data>.json`) e o report (`.html`).

- `examples/`: um arquivo por caso de uso; recebe o `ModelDecision` da factory por injeção de dependência.
- `execution/results.py`: modelo neutro de resultados/trace, produzido pelos exemplos e consumido pelo report.
- `report/html_report.py`: gera o HTML a partir de um `RunResult` (em memória ou do JSON), sem executar exemplos.
