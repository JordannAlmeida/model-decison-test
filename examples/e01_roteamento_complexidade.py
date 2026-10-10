"""1. Roteamento dinâmico por complexidade da entrada (LLM routing).

O modelo de decisão lê a mensagem do usuário e decide se ela vai para um LLM leve e barato
ou para um LLM robusto. Duas perguntas na mesma chamada (Choice + Score) são combinadas em
código num único sinal de complexidade.
"""

from examples.base import Example, normalized
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, ScoreQuestion, Type

LIGHT = "modelo leve"
ROBUST = "modelo robusto"
# below 0.5 so the doubtful zone errs on the side of answer quality
ROBUST_THRESHOLD = 0.45
# illustrative price of one answer, in US$
COST = {LIGHT: 0.002, ROBUST: 0.030}

QUESTIONS = {
    "complexidade": ChoiceQuestion(
        type=Type.CHOICE,
        instructions={
            "pergunta": "Que tipo de modelo de IA é necessário para responder bem à `mensagem_atual`?",
            "foco": "Avalie o raciocínio que a tarefa exige, não o tamanho do texto.",
        },
        criteria={
            "simples": {
                "o_que": "Saudação, pergunta factual direta, tradução curta, conversão ou definição; "
                         "um modelo leve responde em poucas frases.",
                "exemplos": ["Qual a capital do Chile?", "Traduza 'bom dia' para o inglês"],
            },
            "raciocinio_avancado": {
                "o_que": "Exige raciocínio em várias etapas: análise, comparação de alternativas, "
                         "planejamento, demonstração, cálculo não trivial ou código.",
                "exemplos": ["Compare duas estratégias de investimento e recomende uma",
                             "Implemente um algoritmo e explique a complexidade"],
            },
        },
    ),
    "esforco": ScoreQuestion(
        type=Type.SCORE,
        instructions="Quanto esforço de raciocínio é necessário para responder à `mensagem_atual`?",
        criteria=[
            "Resposta direta em uma frase, sem raciocínio",
            "Explicação curta com um ou dois passos",
            "Análise em várias etapas, com comparação, demonstração, cálculo ou código",
        ],
    ),
}

REGULAR = [
    ("Saudação", "Bom dia! Tudo bem por aí?", LIGHT),
    ("Fato geográfico", "Qual é a capital da Austrália?", LIGHT),
    ("Porcentagem simples", "Quanto é 15% de 200?", LIGHT),
    ("Tradução curta", "Traduza 'obrigado pela ajuda' para o inglês.", LIGHT),
    ("Horário de atendimento", "Que horas a loja do centro abre no sábado?", LIGHT),
    ("Comparação financeira",
     "Compare os sistemas de amortização SAC e Price para um financiamento imobiliário de 30 anos, "
     "considerando inflação e amortizações extras, e recomende um para um casal com renda variável.",
     ROBUST),
    ("Algoritmo com código",
     "Escreva uma função em Python que encontre o menor caminho em um grafo com pesos negativos, "
     "detecte ciclos negativos e explique a complexidade.",
     ROBUST),
    ("Plano estratégico",
     "Minha startup tem 18 meses de caixa, churn de 4% ao mês e CAC subindo. Monte um plano de "
     "prioridades para os próximos dois trimestres justificando cada escolha.",
     ROBUST),
]

TRICKY = [
    ("Curta e complexa: demonstração", "Prove que a raiz quadrada de 2 é irracional.", ROBUST),
    ("Curta e complexa: equação", "Resolva x³ − 6x² + 11x − 6 = 0 e mostre os passos.", ROBUST),
    ("Longa e simples: fuso horário",
     "Oi! Então, vou viajar mês que vem com minha família, é a primeira vez que a gente sai do país "
     "e está todo mundo animado. Já compramos as passagens, reservamos o hotel perto do centro e "
     "minha filha montou até uma playlist para o voo. Minha mãe vai junto e está preocupada com o "
     "horário dos remédios dela. Enfim, só queria saber: qual é o fuso horário de Lisboa?",
     LIGHT),
    ("Jargão, mas simples", "O que significa a sigla FGTS?", LIGHT),
    ("Parece técnico, mas é consulta", "Qual comando do git mostra o histórico de commits?", LIGHT),
    ("Simples no texto, complexo na tarefa",
     "Revise este contrato de locação de 40 páginas e me diga quais cláusulas são abusivas.",
     ROBUST),
]

TECHNICAL_TURNS = [
    "Estou montando a planilha de fluxo de caixa da empresa para 2027 e preciso projetar três cenários.",
    "Considere receita recorrente de 120 mil por mês com crescimento de 3% ao mês no cenário base.",
    "No cenário pessimista o churn sobe para 6% e o CAC aumenta 40% por causa da concorrência.",
    "Quero também simular a captação de uma dívida de 2 milhões com carência de 12 meses e juros de 1,4% ao mês.",
    "Como fica o ponto de equilíbrio se a folha de pagamento crescer 15% em julho com o dissídio?",
]
CASUAL_TURNS = [
    "Kkkk verdade, aquele filme é muito bom mesmo, já vi umas três vezes.",
    "Sim, o final é meio previsível, mas a trilha sonora compensa demais.",
    "Você viu que vai ter continuação? Saiu o trailer ontem.",
    "Ah, legal! Vou ver no fim de semana com a galera, a gente sempre faz noite do cinema.",
    "Haha, pipoca doce ou salgada? Eu sou time salgada sem dúvida.",
]


class ComplexityRoutingExample(Example):
    number = 1
    slug = "roteamento-complexidade"
    title = "Roteamento dinâmico por complexidade (LLM routing)"
    summary = ("Avalia a complexidade da mensagem para decidir entre um LLM leve/barato e um LLM "
               "robusto, reduzindo custo sem perder qualidade nas perguntas difíceis.")

    def scenarios(self) -> list[Scenario]:
        cases = [self._route(label, {"mensagem_atual": text}, text, expected)
                 for label, text, expected in REGULAR]
        return [Scenario(
            title="Mensagens típicas de um chat",
            description="Perguntas claramente simples e claramente complexas.",
            cases=cases,
            metrics=_savings(cases),
        )]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [self._route(label, {"mensagem_atual": text}, text, expected)
                  for label, text, expected in TRICKY]
        long_history = [
            self._route(
                "Histórico técnico longo + agradecimento",
                {"historico": _history(TECHNICAL_TURNS, rounds=6), "mensagem_atual": "Valeu, era só isso! Obrigado 😊"},
                "60 mensagens sobre fluxo de caixa; mensagem atual: 'Valeu, era só isso! Obrigado 😊'",
                LIGHT,
            ),
            self._route(
                "Histórico casual longo + pedido complexo",
                {"historico": _history(CASUAL_TURNS, rounds=6),
                 "mensagem_atual": "Mudando de assunto: monte um modelo de precificação para um SaaS B2B com "
                                   "três planos, justificando cada faixa com base em CAC, LTV e churn."},
                "60 mensagens de conversa casual; mensagem atual: modelo de precificação SaaS B2B",
                ROBUST,
            ),
        ]
        return [
            Scenario(
                title="Tamanho do texto ≠ complexidade",
                description="Perguntas curtas que exigem raciocínio e textos longos com pedidos triviais.",
                bonus=True,
                stress="Confundir comprimento, jargão ou formato técnico com complexidade real.",
                cases=tricky,
                metrics=_savings(tricky),
            ),
            Scenario(
                title="Mensagem atual no fim de um histórico longo",
                description="O histórico (~60 mensagens) vem antes da mensagem a ser roteada, em ordem cronológica.",
                bonus=True,
                stress="State grande: a mensagem decisiva fica no fim e pode ser truncada pelo contexto do modelo.",
                cases=long_history,
                metrics=_savings(long_history),
            ),
        ]

    def _route(self, label: str, state: dict, summary: str, expected: str) -> Case:
        call = self._ask(state, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)

        p_advanced = call.choice("complexidade").probabilities["raciocinio_avancado"]
        effort = normalized(call.score("esforco"))
        signal = (p_advanced + effort) / 2
        route = ROBUST if signal >= ROBUST_THRESHOLD else LIGHT
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=route,
            expected=expected,
            passed=route == expected,
            details={
                "P(raciocínio avançado)": round(p_advanced, 3),
                "esforço normalizado": round(effort, 3),
                "sinal combinado": round(signal, 3),
                "limiar p/ robusto": ROBUST_THRESHOLD,
            },
        )


def _history(turns: list[str], rounds: int) -> list[dict]:
    messages = []
    for index in range(rounds):
        for turn in turns:
            messages.append({"autor": "usuario", "texto": turn})
            messages.append({"autor": "assistente", "texto": f"Certo, anotado (parte {index + 1})."})
    return messages


def _savings(cases: list[Case]) -> dict:
    routed = [case.outcome for case in cases if case.outcome in COST]
    if not routed:
        return {}
    actual = sum(COST[route] for route in routed)
    always_robust = COST[ROBUST] * len(routed)
    return {
        "enviadas ao modelo leve": routed.count(LIGHT),
        "enviadas ao modelo robusto": routed.count(ROBUST),
        "custo estimado (US$)": round(actual, 3),
        "custo se tudo fosse ao robusto (US$)": round(always_robust, 3),
        "economia estimada": f"{1 - actual / always_robust:.0%}",
    }
