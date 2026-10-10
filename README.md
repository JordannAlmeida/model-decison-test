# Modelos de decisão: Laya × Jev

Bateria de 12 casos de uso, em português, para avaliar modelos de decisão do tipo *System One* (`POST /v1/systemone`).
Esses modelos não geram texto: recebem um **state** e perguntas tipadas (`choice`, `score`, `noul`) e devolvem
probabilidades. A decisão final fica no código.

- **Jev** (TypeSafe): modelo hospedado (`jev-1.13.0`).
- **Laya**: alternativa open source com a mesma API, rodando local em Docker.

Cada caso de uso tem cenários normais e cenários bônus ("teste de fogo"), pensados para levar o modelo ao limite.

## Casos de uso

1. Roteamento por complexidade (LLM routing)
2. Avaliação de respostas de agentes (LLM-as-a-Judge)
3. Reranking de trechos em RAG
4. Triagem de e-mails
5. Risco de churn
6. Validação de formulários
7. Triagem de suporte
8. Guardrails e moderação
9. Lead scoring
10. Sentimento em massa
11. Decisão de NPCs em jogos
12. Pré-atendimento especializado (advocacia e clínica)

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

## Resultados

Mesmo código, mesmas entradas, ~167 casos com gabarito.

| | Laya (padrão) | Laya otimizado | Jev |
|---|---|---|---|
| Cenários normais | 41/82 (50%) | 41/82 (50%) | 79/83 (95%) |
| Teste de fogo | 39/84 (46%) | 47/84 (56%) | 82/84 (98%) |
| **Total** | **80/166 (48%)** | **88/166 (53%)** | **161/167 (96%)** |

| | Laya otimizado | Jev |
|---|---|---|
| Latência mediana | 279 ms | 309 ms |
| Latência p90 | 1.067 ms | 355 ms |
| Duração da bateria | 105 s | 50 s |
| Custo | sem custo por token (infra própria) | US$ 0,042 / M tokens (≈ US$ 0,0067 na bateria) |

Referência de preço: a API de decisão da OpenAI custa US$ 0,10 / M tokens (avaliado em 10/10/2026).

## Conclusões

**Jev**
- Atendeu os 12 casos de uso em português, inclusive nos cenários de estresse (98%). Usa bem a escala inteira,
  compara campos do state, lê states grandes sem perder a informação decisiva e lida com 30–40 opções.
- Dos 6 erros, só 1 ou 2 são falhas claras; o restante vem de ambiguidade nos critérios ou no gabarito, em geral
  com margem baixa (capturável por limiares de escalonamento).
- Para produção: limiares por risco da ação, prioridades entre regras no código (não no modelo) e níveis/Nouls
  específicos para sinais implícitos (ex.: churn silencioso).

**Laya**
- Na configuração padrão (48%), truncava o state em ~1.000 tokens, roteava português curto para o checkpoint em
  inglês e falhava com muitas opções.
- Ajustes só na chamada e no container (`model=multilingual`, `max_len=8192`, `head_max_len=1024`, torneio de
  opções, 12 threads) levaram a 53%: sem truncamento, 8/10 nas Choices grandes e latência mediana menor que a do Jev
  em states curtos. Vale manter essa configuração.
- O restante da distância (53% × 96%) é do modelo, não da configuração: Nouls saturam (respondem quase sempre a
  mesma coisa), Choices erram com probabilidade alta, Scores ficam no meio da escala e as probabilidades não são
  calibradas. Ler o state inteiro não garante usá-lo bem.
- Aceitável apenas em recortes estreitos: julgamentos sobre um único texto, Noul sem `criteria`, Choices
  resolvidas por torneio, e sempre com validação própria por caso de uso, sem usar a probabilidade como confiança.
- Vantagens: roda local (dados não saem do ambiente), sem custo por token, determinístico e informa truncamento.

**Recomendação:** usar o Jev quando a qualidade da decisão importa; considerar o Laya só para dados que não podem
sair do ambiente, nos recortes acima.

**Ressalvas:** amostra pequena com gabaritos próprios (alguns discutíveis); cada provider rodou uma vez; testes em
inglês, GPU, ajuste fino e calibração do Laya ficaram para próximos passos.

## Documentação

- [`docs/avaliacao-laya-vs-jev.md`](docs/avaliacao-laya-vs-jev.md): cenários, metodologia e resultados completos.
- [`docs/avaliacao-laya-otimizado.md`](docs/avaliacao-laya-otimizado.md): ajustes de configuração do Laya e efeito de cada um.
- [`docs/implementation-emaples.md`](docs/implementation-emaples.md): especificação dos 12 casos de uso.
- [`docs/precos-modelos.md`](docs/precos-modelos.md): preços por milhão de tokens.
