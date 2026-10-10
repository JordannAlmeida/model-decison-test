# Laya otimizado: configuração e resultado nos 12 casos de uso

## 1. Resumo

Este documento continua a [avaliação Laya × Jev](avaliacao-laya-vs-jev.md). Lá, o Laya rodou com a configuração
padrão e acertou 48% dos casos. Aqui, a configuração foi ajustada a partir da documentação do Laya, sem mudar
nenhum exemplo, pergunta ou gabarito, e a bateria foi executada de novo.

| | Laya (report original) | Laya otimizado | Jev |
|---|---|---|---|
| Cenários normais | 41/82 (50%) | 41/82 (50%) | 79/83 (95%) |
| Teste de fogo | 39/84 (46%) | 47/84 (**56%**) | 82/84 (98%) |
| Total | 80/166 (48%) | 88/166 (**53%**) | 161/167 (96%) |

- **Ganho de 8 casos (+5 pontos percentuais), sem nenhuma regressão.** Mudaram só três cenários bônus: histórico
  longo no roteamento (0/2 → 1/2), taxonomia com 30 subfilas (1/5 → 3/5) e lista com 40 especialidades
  (0/5 → 5/5).
- **O que a configuração resolveu:** truncamento do state (20 chamadas → 0), roteamento de português para o
  checkpoint em inglês (3 chamadas → 0) e Choices com muitas opções (1/10 → 8/10).
- **O que a configuração não resolve:** Nouls que saturam, Choices erradas com probabilidade alta, Scores presos
  no meio da escala e raciocínio sobre estado estruturado. Os 28 acertos que vinham de o Laya responder sempre a
  mesma coisa nos exemplos 2, 5, 6 e 8 continuam lá. States longos quase não melhoraram: o modelo agora lê o
  state inteiro, mas acerta 7 de 20 nesses cenários (antes, 6).
- A distância para o Jev caiu de 48 para 43 pontos percentuais.

---

## 2. Ponto de partida e restrições

- **O que podia mudar:** só a chamada ao Laya (`modelDecision/laya/integration.py`) e os parâmetros de execução do
  container (`run-laya-server.sh`). Exemplos, perguntas, gabaritos, regras de decisão e o código-fonte do Laya
  ficaram intactos.
- **Fontes consultadas:** README, `docs/` (a fonte do site <https://nandhakishorm.github.io/laya/>), `BENCHMARKS.md`
  e o código do servidor no repositório local do Laya (`/home/linux/code/laya`, release 0.4.2, commit `6880462`).
- **Mesmo modelo nas duas execuções:** checkpoint `multilingual` na revisão `7b928d8`, em CPU (AMD Ryzen 9 5900X,
  12 núcleos físicos) e Docker. Com a configuração padrão, a bateria reproduziu os 80/166 do report original, com a
  mesma decisão em todos os casos e probabilidades que diferem no máximo 0,0004 (arredondamento pela mudança no
  número de threads). Assim, a comparação isola o efeito da configuração.

| Execução | Data | Configuração | Trace / report |
|---|---|---|---|
| Laya (report original) | 10/10/2026 14:09 | padrão, 4 threads | `output/run_laya_20261010-140932.{json,html}` |
| Laya otimizado | 10/10/2026 16:06 | seção 4, 12 threads | `output/run_laya_20261010-160639.{json,html}` |
| Jev | 10/10/2026 14:34 | `jev-1.13.0` | `output/run_jev_20261010-143405.{json,html}` |

---

## 3. Diagnóstico: o que dava para resolver por configuração

Cada limitação da seção 4.4 do report original foi confrontada com os controles que a API HTTP do Laya aceita
(`model`, `task`, `lang`, `max_len`, `head_max_len`, `min_confidence` e, por pergunta, `labels` e `option_order`)
e com as variáveis de ambiente do servidor.

| # | Limitação no report original | Causa encontrada | Controle disponível |
|---|---|---|---|
| 1 | Janela de ~1.000 tokens, com corte do fim do state | O checkpoint multilíngue lê até 8.192 tokens, mas vem configurado com `max_len` 1.024 | `max_len` por requisição |
| 2 | Nouls que saturam | O Noul reage a palavras em comum entre a pergunta e o state (seção 5.2) | `labels`, `option_order`, Noul como Choice: testados, sem ganho |
| 3 | Multiclasse com erros confiantes | Modelo base sem ajuste fino, sem temperaturas calibradas no checkpoint multilíngue | Nenhum na chamada |
| 4 | Scores comprimidos no meio da escala | Viés de posição do checkpoint multilíngue em Score (#131 no repositório do Laya) e falta de calibração | `option_order` (média entre ordens): testado, pior |
| 5 | Muitas opções | As opções dividem um limite de 256 tokens (`head_max_len`) | `head_max_len` e torneio de opções |
| 6 | Raciocínio sobre estado estruturado (NPC) | Capacidade do modelo | Nenhum |
| 7 | Português sem acento roteado para o checkpoint em inglês | Detecção heurística de idioma do roteador | `model` ou `lang` |
| 8 | Latência em CPU cresce com o state | Servidor limitado a 4 threads numa máquina com 12 núcleos | `LAYA_THREADS` |

**Medição do orçamento de tokens.** Para não depender de estimativa, os heads (instrução + opções) de todas as 34
perguntas dos exemplos foram tokenizados com o próprio tokenizer do checkpoint, dentro do container:

| Pergunta | Opções | Head com limite de 256 (padrão) | Head com limite de 1.024 |
|---|---|---|---|
| Exemplo 7, `subfila` | 30 | 255 tokens, 8 tokens por opção | 471 tokens, sem corte |
| Exemplo 12, `area` (lista ampla) | 40 | 259 tokens, 6 tokens por opção | 566 tokens, sem corte |
| As outras 32 perguntas | 2 a 8 | 37 a 218 tokens, sem corte | igual |

Ou seja, o limite de 256 só cortava as duas perguntas com muitas opções. O código do Laya também limita cada opção
a 48 tokens, independentemente de qualquer parâmetro. Só três opções passam desse limite: as duas de
`complexidade` (exemplo 1, até 68 tokens) e uma de `categoria` (exemplo 4, 60 tokens).

---

## 4. Ajustes aplicados

### 4.1 Chamada ao Laya (`modelDecision/laya/integration.py`)

```mermaid
flowchart LR
    ex[examples/e01..e12] --> call[LayaModelDecision.call]
    call --> cfg["model = multilingual<br/>max_len = 8192<br/>head_max_len = 1024"]
    cfg --> big{Choice com mais<br/>de 16 opções?}
    big -- não --> final[POST /v1/systemone]
    big -- sim --> rounds["rodada do torneio<br/>grupos de até 16 opções"]
    rounds --> final
    final --> resp["Response<br/>(eliminadas com probabilidade 0)"]
```

| Ajuste | Valor | Por quê |
|---|---|---|
| `model` | `multilingual` | O roteador detectava português curto sem acento como inglês. Um `model` que já nomeie um checkpoint do Laya (`english`, `multilingual`, `typed-decisions`) é respeitado; qualquer outro, como `laya-latest`, vira `multilingual`. |
| `max_len` | 8.192 | Janela máxima do checkpoint multilíngue e teto padrão do servidor. O maior state da bateria tem 3.232 tokens, então nada é cortado. O README indica 16–18 acertos em 20 até ~4.000 tokens e resultados variáveis acima disso. |
| `head_max_len` | 1.024 | Teto, não tamanho fixo: o head só usa o que precisa, e as perguntas com até 8 opções ficam idênticas. As de 30 e 40 opções passam a caber sem corte. Um limite de 2.048 deu o mesmo resultado. |
| Torneio | grupos de até 16 | Reproduz via HTTP o `laya.predict_tournament`: as opções são divididas em grupos, cada grupo vira uma pergunta (todas na mesma chamada), e a pergunta original é refeita só com os vencedores. Com 30 ou 40 opções, são duas chamadas em vez de uma. |

Exemplo do corpo enviado (as perguntas seguem iguais às do exemplo):

```json
{
  "state": {"canal": "WhatsApp", "mensagem": "Tenho um zumbido no ouvido há meses"},
  "model": "multilingual",
  "max_len": 8192,
  "head_max_len": 1024,
  "questions": {"area": {"type": "choice", "instructions": "...", "criteria": {"...": "..."}}}
}
```

No torneio, as probabilidades da Choice são só sobre os finalistas, como na implementação do Laya. As opções
eliminadas voltam com probabilidade 0, para que a resposta mantenha o formato do Jev, com todas as opções.

### 4.2 Container (`run-laya-server.sh`)

| Variável | Valor | Por quê |
|---|---|---|
| `LAYA_THREADS` / `OMP_NUM_THREADS` | núcleos físicos (12 nesta máquina) | A doc recomenda até o número de núcleos físicos; o padrão do compose era 4 |
| `LAYA_PRELOAD` / `LAYA_MODELS` | `1` / `multilingual` | Carrega na subida o único checkpoint que a chamada usa, em vez de na primeira requisição |
| `LAYA_DEFAULT_MODEL` | `multilingual` | Fallback do roteador, caso alguma chamada não fixe o checkpoint |
| `LAYA_MAX_TOKEN_BUDGET` | 8.192 | Teto para o `max_len` e o `head_max_len` enviados pela chamada (explicita o padrão) |

---

## 5. O que foi testado e ficou de fora

### 5.1 Variantes da chamada

As variantes rodaram num harness separado, que executa os mesmos exemplos com a chamada modificada. A referência é
a configuração da seção 4 sem o torneio (86/166).

| Variante | Onde | Resultado | Referência | Veredito |
|---|---|---|---|---|
| Noul com `labels` A/B | exemplos 2, 3, 5, 6, 8, 9 e 12 | 43/84 | 46/84 | pior |
| Noul com `labels` sim/não | idem | 46/84 | 46/84 | igual |
| Noul com média entre as duas ordens (`option_order`) | idem | 46/84, ~2× mais lento | 46/84 | igual |
| Noul como Choice de 2 opções (A/B) | idem | 44/84 | 46/84 | pior |
| Noul como Choice de 2 opções (sim/nao) | idem | 45/84 | 46/84 | pior |
| Média entre as rotações das opções em Score e Choice | bateria inteira | 82/166, 310 s | 86/166, 107 s | pior e 3× mais lento |
| State em texto "campo: valor" em vez de JSON | bateria inteira | 83/166 | 86/166 | pior |
| Checkpoint `english` | bateria inteira | 66/166, 336 s | 86/166 | pior |
| Checkpoint `typed-decisions` | bateria inteira | 60/169, 338 s | 86/166 | pior |
| `head_max_len` 2.048 | exemplos 7 e 12 | 14/35 | 14/35 | igual |
| Torneio com grupos de 8 | exemplos 7 e 12 | 14/35 | 16/35 (grupos de 16) | pior |

- Os checkpoints `english` e `typed-decisions` usam o ModernBERT-large em inglês. O README mostra que o
  `typed-decisions` sobe de 0,36 para 0,77 no benchmark de decisões tipadas, mas em inglês; em português, ele ficou
  abaixo do multilíngue.
- A média entre ordens é a técnica que o README sugere contra o viés de posição. Aqui ela piorou os casos claros:
  no exemplo 1, os casos normais caíram de 8/8 para 6/8.

### 5.2 Por que nenhuma forma de enviar o Noul resolveu

Uma sonda com 9 mensagens de churn de gabarito conhecido mediu o Noul `pedido_cancelamento` (sem `criteria`) em três
formatos de state:

| Formato do state | "Oi! Como cadastro um novo entregador?" | "Vocês têm desconto anual?" | "Preciso cancelar o pedido 4471" | "Quero cancelar meu plano" | AUC (9 mensagens) |
|---|---|---|---|---|---|
| `{cliente, conversa: […]}` (formato do exemplo 5) | 0,88 | 0,96 | 1,00 | 1,00 | 0,94 |
| `{"mensagem": …}` | 0,03 | 0,00 | 1,00 | 1,00 | 0,89 |
| Texto puro | 0,04 | 0,00 | 0,99 | 1,00 | 1,00 |

- **O formato move a calibração, não a discriminação.** Com os dados do cliente no state (que trazem
  "plano: Delivery Pro"), qualquer mensagem sobe para perto de 1. O motivo provável é que a pergunta fala em
  "cancelar o plano" e o modelo reage às palavras em comum.
- **"Cancelar" fora de contexto fica em 0,99–1,00** nos três formatos com a renderização padrão. As renderizações
  alternativas (`labels`, `criteria` sim/não, ordem invertida, Choice A/B) baixam esse valor em alguns formatos,
  mas baixam junto os pedidos reais. A AUC fica entre 0,78 e 1,00 em todas as combinações, sem uma variante
  consistentemente melhor.
- No Noul `cita_concorrente`, o formato que derruba os falsos positivos também derruba o verdadeiro:
  "Um amigo usa o RotaFácil" cai de 0,96 para 0,01–0,02 (AUC 0,79 → 0,57–0,71).
- Mudar o formato do state seria mexer no desenho dos exemplos, e mesmo assim a variante em texto "campo: valor"
  piorou a bateria inteira (5.1).

---

## 6. Resultados

### 6.1 Efeito de cada ajuste

| Configuração | Total | Duração da bateria |
|---|---|---|
| Padrão, 4 threads (report original) | 80/166 | 129 s |
| Padrão, 12 threads | 80/166 (mesmas decisões) | 72 s |
| + `model` multilingual, `max_len` 8.192, `head_max_len` 1.024 | 86/166 | 107 s |
| + torneio com grupos de 16 (**configuração final**) | **88/166** | 105 s |

- **Threads:** não mudam nenhuma decisão (as probabilidades diferem no máximo 0,0004), só a velocidade.
- **Checkpoint e janelas (+6):** histórico longo 0 → 1, 30 subfilas 1 → 4 e 40 especialidades 0 → 2. Ler o state
  longo inteiro custa tempo: 72 → 107 s.
- **Torneio (+2):** 40 especialidades 2 → 5, mas 30 subfilas 4 → 3 (perde "perfil", que acertava com probabilidade
  0,21).

### 6.2 Por exemplo

| # | Caso de uso | Laya (original) | Laya otimizado | Jev |
|---|---|---|---|---|
| 1 | Roteamento por complexidade | 12/16 | **13/16** | 16/16 |
| 2 | LLM-as-a-Judge | 5/11 | 5/11 | 10/11 |
| 3 | Reranking em RAG | 3/5 | 3/5 | 5/5 |
| 4 | Triagem de e-mails | 5/13 | 5/13 | 13/13 |
| 5 | Risco de churn | 8/15 | 8/15 | 14/15 |
| 6 | Validação de formulários | 7/12 | 7/12 | 12/12 |
| 7 | Triagem de suporte | 2/17 | **4/17** | 17/17 |
| 8 | Guardrails | 9/13 | 9/13 | 12/13 |
| 9 | Lead scoring | 5/10 | 5/10 | 10/10 |
| 10 | Sentimento em massa | 10/20 | 10/20 | 20/20 |
| 11 | NPC de jogo | 7/16 | 7/16 | 14/17 |
| 12 | Pré-atendimento | 7/18 | **12/18** | 18/18 |

### 6.3 Por cenário (B = teste de fogo; em negrito, os que mudaram)

| # | Cenário | Laya (original) | Laya otimizado | Jev |
|---|---|---|---|---|
| 1 | Mensagens típicas de um chat | 8/8 | 8/8 | 8/8 |
| 1 | B · Tamanho do texto ≠ complexidade | 4/6 | 4/6 | 6/6 |
| 1 | **B · Mensagem atual no fim de um histórico longo** | 0/2 | **1/2** | 2/2 |
| 2 | Respostas de um agente de trocas e devoluções | 1/5 | 1/5 | 4/5 |
| 2 | B · Alucinações sutis | 3/4 | 3/4 | 4/4 |
| 2 | B · Fonte oficial extensa | 1/2 | 1/2 | 2/2 |
| 3 | Base de conhecimento de uma construtora | 1/2 | 1/2 | 2/2 |
| 3 | B · Distratores e perguntas compostas | 2/2 | 2/2 | 2/2 |
| 3 | B · Trecho longo com a resposta enterrada | 0/1 | 0/1 | 1/1 |
| 4 | Caixa de entrada corporativa | 1/6 | 1/6 | 6/6 |
| 4 | B · E-mails ambíguos e disfarçados | 2/5 | 2/5 | 5/5 |
| 4 | B · Thread longa encaminhada | 2/2 | 2/2 | 2/2 |
| 5 | Conversa que piora a cada rodada | 2/5 | 2/5 | 5/5 |
| 5 | Mensagens avulsas | 2/3 | 2/3 | 3/3 |
| 5 | B · Linguagem enganosa | 3/5 | 3/5 | 4/5 |
| 5 | B · Histórico longo com virada na última mensagem | 1/2 | 1/2 | 2/2 |
| 6 | Sinistros e pedidos de reembolso | 4/6 | 4/6 | 6/6 |
| 6 | B · Textos que enganam | 3/4 | 3/4 | 4/4 |
| 6 | B · Relato longo | 0/2 | 0/2 | 2/2 |
| 7 | Chamados do dia | 1/6 | 1/6 | 6/6 |
| 7 | B · Sinais enganosos de urgência e de setor | 0/4 | 0/4 | 4/4 |
| 7 | **B · Taxonomia com 30 subfilas** | 1/5 | **3/5** | 5/5 |
| 7 | B · Chamado com log extenso | 0/2 | 0/2 | 2/2 |
| 8 | Respostas de um chatbot de e-commerce | 4/6 | 4/6 | 5/6 |
| 8 | B · Violações sutis | 4/5 | 4/5 | 5/5 |
| 8 | B · Manual de políticas extenso | 1/2 | 1/2 | 2/2 |
| 9 | Carteira de leads de um lançamento | 2/5 | 2/5 | 5/5 |
| 9 | B · Sinais contraditórios | 2/4 | 2/4 | 4/4 |
| 9 | B · Histórico de interações extenso | 1/1 | 1/1 | 1/1 |
| 10 | Lote de avaliações da semana | 6/12 | 6/12 | 12/12 |
| 10 | B · Linguagem difícil | 4/6 | 4/6 | 6/6 |
| 10 | B · Avaliação longa | 0/2 | 0/2 | 2/2 |
| 11 | Situações isoladas | 2/5 | 2/5 | 4/5 |
| 11 | Partida simulada | 3/5 | 3/5 | 5/6 |
| 11 | B · Personalidade e conflitos de prioridade | 2/4 | 2/4 | 3/4 |
| 11 | B · Cena lotada | 0/2 | 0/2 | 2/2 |
| 12 | Escritório de advocacia | 3/4 | 3/4 | 4/4 |
| 12 | Clínica médica | 1/4 | 1/4 | 4/4 |
| 12 | B · Fronteiras e riscos | 3/5 | 3/5 | 5/5 |
| 12 | **B · Lista ampla com 40 especialidades** | 0/5 | **5/5** | 5/5 |

### 6.4 Teste de fogo por família de estresse

| Família | Laya (original) | Laya otimizado | Jev |
|---|---|---|---|
| State grande e posição da informação | 6/20 | 7/20 | 20/20 |
| Sinais superficiais enganosos | 6/8 | 6/8 | 8/8 |
| Linguagem difícil e intenção ambígua | 9/16 | 9/16 | 15/16 |
| Detalhe sutil e adversarial | 10/13 ¹ | 10/13 ¹ | 13/13 |
| Muitas opções | 1/10 | **8/10** | 10/10 |
| Fronteiras, contexto e conflito de regras | 7/17 | 7/17 | 16/17 |

¹ Como no report original, todos esses acertos vêm de o Laya bloquear ou escalar tudo nesses exemplos (seção 7,
limitação 2).

### 6.5 Desempenho operacional

| | Laya (original) | Laya otimizado | Jev |
|---|---|---|---|
| Onde roda | Docker, CPU, 4 threads | Docker, CPU, 12 threads | API hospedada |
| Chamadas no trace / erros | 201 / 0 | 201 / 0 ² | 202 / 0 |
| Checkpoint que respondeu | 198 `multilingual` + 3 `english` | 201 `multilingual` | — |
| Tokens de entrada | 123,9 mil (após o truncamento) | 158,0 mil (sem truncamento) ² | 160,2 mil |
| Chamadas truncadas | 20 (até 2.351 tokens perdidos) | **0** | 0 |
| Latência mediana | 462 ms | 279 ms | 309 ms |
| Latência p90 | 1.088 ms | 1.067 ms | 355 ms |
| Mediana com < 600 tokens de entrada | 329 ms | 201 ms | 315 ms |
| Mediana com ≥ 1.000 tokens de entrada | 1.002 ms | 514 ms | 308 ms |
| Maior latência | 5,98 s (manual de 85 regras, truncado) | 7,48 s (log extenso, 3.232 tokens de state) | 0,62 s |
| Duração da bateria completa | 129 s | 105 s | 50 s |

² As rodadas do torneio são feitas dentro da mesma chamada do `ModelDecision`. O trace registra uma chamada por
caso, com a latência de todas as rodadas, mas o `usage` só da chamada final. Na prática, foram 211 requisições
HTTP.

- As threads explicam a queda da mediana: com states curtos, o Laya em CPU fica mais rápido que a API do Jev.
- O pior caso subiu porque o modelo agora lê o state inteiro. O manual de 85 regras foi de 6,0 s (truncado) para
  7,0 s (inteiro), e os dois logs extensos levaram 7,0–7,5 s.
- As perguntas com torneio levaram 340–440 ms, contra ~280 ms numa chamada única.

---

## 7. Situação das limitações após a otimização

| # | Limitação (report original) | Situação |
|---|---|---|
| 1 | Janela de contexto com corte do fim do state | **Resolvida na configuração**, mas o modelo não usa bem o state longo |
| 2 | Nouls que saturam | Inalterada |
| 3 | Multiclasse com erros confiantes | Inalterada |
| 4 | Scores comprimidos | Inalterada |
| 5 | Muitas opções | **Resolvida em grande parte** (1/10 → 8/10) |
| 6 | Raciocínio sobre estado estruturado | Inalterada |
| 7 | Roteamento de idioma | **Resolvida** |
| 8 | Latência em CPU | Melhorou em states curtos; o pior caso subiu |

**1. State longo: agora é lido, mas a decisão continua errada.** Os pares de entradas que davam números idênticos
no report original agora dão números diferentes, prova de que o fim do state chega ao modelo. Mesmo assim, só um
cenário de state grande passou a acertar:

| Caso | Antes (truncado) | Agora (inteiro) | Resultado |
|---|---|---|---|
| Histórico técnico + "Valeu, era só isso!" (exemplo 1) | `mensagem_atual` cortada; sinal 0,452 → robusto | P(raciocínio avançado) 0,13; sinal 0,377 → leve | **passou a acertar** |
| Histórico casual + pedido de modelo de precificação (exemplo 1) | `mensagem_atual` cortada; sinal 0,438 | P(raciocínio avançado) 0,09; sinal 0,416 → leve | continua errado |
| Avaliação longa: denúncia de falsificação × controle (exemplo 10) | notas 3,44 e 3,44 | notas 3,23 e 3,43; tema "produto" 0,69 com a denúncia | continua errado: a denúncia *baixou* a nota |
| Fonte longa: resposta correta × alucinada (exemplo 2) | sinais idênticos | alucinação 0,99 e 0,98 | continua tudo para humano |
| Manual de 85 regras: desconto de 10% × 25% (exemplo 8) | `desconto_indevido` 0,84 nos dois | `desconto_indevido` 1,00 nos dois | continua bloqueando tudo |
| Log extenso, impacto no fim (exemplo 7) | setor "outro" 0,55 | setor "técnico" 0,74, prioridade 1,42 (média) | setor certo, prioridade errada |
| Relato longo, acidente no fim (exemplo 6) | coerente 0,93, suficiência 0,90 | coerente 0,97, suficiência 1,04, conteúdo indevido 0,97 | continua bloqueando |
| Cena lotada (exemplo 11) | atacar 0,75 e 0,60 | atacar 0,68 e 0,60 | continua atacando |

**2. Nouls que saturam.** Nada mudou nos exemplos 2, 5, 6 e 8: 11/11 para humano, 14/15 alerta, 12/12 bloquear e
13/13 bloquear, com os mesmos valores do report original nos states curtos (por exemplo, alucinação entre 0,96 e
1,00 nas 11 respostas). Os **28 acertos** que vêm dessa resposta fixa agora são 28 de 88. As renderizações que a
documentação sugere não separaram os casos (seção 5).

**3. Multiclasse com erros confiantes.** Com states curtos, os valores são os mesmos do report original:
"Erro no sistema" → spam (0,98), nota fiscal de fornecedor → cancelamento (0,90), "Relatório com contorno" → vendas
(1,00). Nos e-mails, "cancelamento" continua saindo em 6 de 13 mensagens.

**4. Scores comprimidos.** A prioridade continua entre 0,76 e 2,39 ("sistema inteiro fora do ar" em 1,93), a nota
de insatisfação entre 2,1 e 4,7, e o risco de churn nunca chega ao nível 3. O máximo subiu de 2,27 para 2,77, mas
só no histórico longo que agora é lido inteiro.

**5. Muitas opções.** É o maior ganho. Com o limite de 1.024 tokens, cada opção é lida inteira; com o torneio,
cada uma disputa num grupo de até 16:

| Caso | Antes | Agora |
|---|---|---|
| Zumbido no ouvido | oftalmologia 0,51 | **otorrinolaringologia 0,98** |
| TSH alterado | obstetrícia 0,96 | **endocrinologia 0,59** |
| Pedra no rim | atendente humano (dermatologia 0,23) | **urologia 0,99** |
| Ronco e apneia | ginecologia 0,63 | **pneumologia 0,74** |
| Dor de dente | atendente humano (dermatologia 0,43) | **odontologia 0,97** |
| Subfila: ponto eletrônico | vendas/novo-contrato 0,22 | **tecnico/ponto-eletronico 0,99** |
| Subfila: nota fiscal | financeiro/cobranca-duplicada 0,15 (checkpoint em inglês) | **financeiro/nota-fiscal 0,87** |
| Subfila: upgrade | vendas/upgrade 0,25 | vendas/upgrade 0,98 |
| Subfila: segurança | vendas/novo-contrato 0,10 | tecnico/relatorios 0,97 |
| Subfila: perfil | financeiro/cobranca-duplicada 0,33 | tecnico/api 0,98 |

Os dois erros restantes vêm com probabilidade alta (0,97–0,98). O torneio concentra a probabilidade nos finalistas,
então essa probabilidade não serve como sinal de confiança.

**6. Raciocínio sobre estado estruturado.** O NPC continua com probabilidades quase planas e "atacar" como saída
padrão (13 de 16 decisões).

**7. Roteamento de idioma.** As 201 chamadas foram para o checkpoint multilíngue. Das duas mensagens em português
que iam para o checkpoint em inglês, a subfila de nota fiscal passou a acertar. A troca de e-mail das notas fiscais
agora acerta o setor (financeiro 0,88), mas segue errando a prioridade (1,36, média, em vez de baixa). O e-mail em
inglês, que antes ia corretamente para o checkpoint em inglês, continua certo no multilíngue (cancelamento 0,79).

**8. Latência.** Ver 6.5.

---

## 8. Ressalvas

- A amostra, os gabaritos e as perguntas são os mesmos do report original. Valem as ressalvas de lá: são cerca de
  167 casos, e alguns gabaritos são discutíveis.
- As variantes da seção 5 foram escolhidas e avaliadas nesta mesma bateria, sem um conjunto separado de validação.
  Os ajustes que entraram são genéricos e documentados pelo Laya (checkpoint, janelas e torneio), não ajustes de
  texto por caso. Mesmo assim, o ganho de 8 casos deve ser confirmado numa amostra maior.
- **O checkpoint fica fixo em `multilingual`, mesmo para texto em inglês.** O README indica que o checkpoint em
  inglês é melhor em inglês (0,820 × 0,710). Com tráfego em inglês relevante, convém mandar `lang` em vez de fixar
  `model`.
- Com o torneio, a probabilidade de uma Choice grande deixa de ser comparável à de uma chamada única. Isso afeta
  regras como "1ª opção abaixo de 0,45 → humano" nos exemplos 7 e 12.
- `run-laya-server.sh` faz `git pull origin main` a cada subida. Uma versão nova do Laya pode mudar os resultados;
  para comparações, convém fixar o commit.
- A GPU da máquina não estava disponível (o `nvidia-smi` acusa "Driver/library version mismatch"), então o
  `compose.cuda.yaml` não foi testado. Isso afetaria só a latência.

---

## 9. Conclusões e recomendações

- **A configuração padrão subaproveitava o Laya em três pontos: janela, idioma e muitas opções.** Os três foram
  corrigidos só na chamada e no container. Vale manter essa configuração para qualquer uso do Laya em português.
- **O resto da distância para o Jev (53% × 96%) é do modelo, não da configuração.** Os Nouls reagem a palavras em
  comum, as Choices erram com confiança alta e os Scores ficam no meio da escala. Isso apareceu com todas as
  variantes de chamada testadas.
- **Recortes em que o Laya otimizado é aceitável** (as condições do report original, revistas):
  - state de qualquer tamanho até ~4.000 tokens, que agora é lido sem corte, mas com validação própria, porque ler
    o state inteiro não garante usar a informação;
  - Choice de qualquer tamanho via torneio, sem usar a probabilidade como confiança;
  - julgamentos sobre um único texto, sem comparar campos do state;
  - Noul sem `criteria`, com state contendo só o texto julgado.
- **Próximos passos, fora do escopo desta otimização:**
  - ajuste fino com decisões em português (o notebook do Laya leva o benchmark de decisões tipadas de 0,36 para
    0,77);
  - calibrar as temperaturas do checkpoint multilíngue com dados de validação próprios (pelo `BENCHMARKS.md`, o ECE
    vai de 0,314 para 0,106). Isso mexe nos limiares e no valor esperado dos Scores, não no argmax;
  - redesenhar as perguntas que comparam campos para olhar um campo por vez, e enviar no state só o campo julgado
    (seção 5.2);
  - testar em GPU, por causa da latência em states longos.

### Como reproduzir

```bash
./run-laya-server.sh                    # sobe o Laya com as variáveis da seção 4.2
uv run python main.py --provider laya   # bateria completa + report HTML em output/
```
