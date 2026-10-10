"""5. Detecção de intenção de cancelamento / risco de churn.

Cada mensagem nova de um cliente reavalia a conversa inteira: um Score dá o risco de churn em
cinco níveis descritos por situações e dois Nouls verificam pedido explícito de cancelamento e
menção a concorrente. O código decide entre nenhuma ação, monitorar ou alertar o Sucesso do Cliente.
"""

from examples.base import Example, normalized
from execution.results import Case, Scenario
from modelDecision.scheme import NoulQuestion, ScoreQuestion, Type

NO_ACTION = "sem ação"
WATCH = "monitorar e oferecer contato proativo"
ALERT = "alerta imediato ao Sucesso do Cliente"

QUESTIONS = {
    "risco_churn": ScoreQuestion(
        type=Type.SCORE,
        instructions="Qual é o risco de o cliente cancelar, considerando principalmente as mensagens mais recentes da `conversa`?",
        criteria=[
            "Satisfeito ou neutro; nenhum sinal de insatisfação",
            "Insatisfação pontual com um problema específico, sem falar em sair",
            "Frustração repetida ou comparação com concorrentes, sem intenção declarada de sair",
            "Ameaça condicional de cancelar, como 'se não resolverem, vou cancelar'",
            "Decisão declarada de cancelar ou de não renovar o contrato",
        ],
    ),
    # no criteria: tested with and without (as the docs suggest); with true/false descriptions
    # the answer stayed near 1 even for compliments
    "pedido_cancelamento": NoulQuestion(
        type=Type.NOUL,
        instructions="O cliente pede explicitamente para cancelar a conta, o plano ou a assinatura?",
    ),
    "cita_concorrente": NoulQuestion(
        type=Type.NOUL,
        instructions="O cliente menciona um concorrente ou outra empresa como alternativa?",
    ),
}

CLIENT = {"empresa": "Padaria Pão Dourado", "plano": "Delivery Pro", "cliente_desde": "2023-03", "chamados_90_dias": 2}

# each round adds a customer message (and the support reply that preceded it)
ROUNDS = [
    (None, "Oi! Como faço para cadastrar um novo entregador no sistema?", NO_ACTION),
    ("Basta ir em Equipe > Novo entregador e preencher os dados.",
     "Tentei cadastrar e deu erro de novo. Já é a segunda vez esta semana que o sistema trava no horário de pico.",
     WATCH),
    ("Sentimos muito! Já abrimos um chamado com o time técnico.",
     "Um amigo usa o RotaFácil e disse que lá não tem esse problema. Estou começando a pensar em trocar.",
     WATCH),
    ("Entendemos a frustração. O time técnico está priorizando a correção.",
     "Se até sexta não resolverem, vou cancelar e migrar para o RotaFácil.",
     ALERT),
    ("A correção foi adiada para a próxima semana, pedimos desculpas.",
     "Não resolveram. Quero cancelar minha assinatura hoje.",
     ALERT),
]

STANDALONE = [
    ("Elogio", "Adorei a nova versão do app, ficou muito mais rápido!", {NO_ACTION}),
    ("Dúvida comercial", "Vocês têm desconto para pagamento anual?", {NO_ACTION}),
    ("Pedido direto de cancelamento", "Quero cancelar meu plano. Não uso mais o serviço.", {ALERT}),
]

TRICKY = [
    ("Sarcasmo", "Nossa, que maravilha, terceira vez que o app cai esta semana. Serviço excelente, recomendo "
                 "para os meus inimigos.", {WATCH, ALERT}),
    ("'Cancelar' um pedido", "Preciso cancelar o pedido 4471, pedi o tamanho errado. Já fiz um novo com o "
                             "tamanho certo.", {NO_ACTION}),
    ("'Cancelar' uma reunião", "Cancelei a reunião de amanhã com o consultor, podemos remarcar para segunda?",
     {NO_ACTION}),
    ("Churn silencioso", "Podem me enviar a exportação completa dos meus dados e as notas fiscais dos últimos 12 "
                         "meses? Também quero saber como remover todos os usuários da equipe.", {WATCH, ALERT}),
    ("Não renovação educada", "Agradeço a atenção de sempre, mas a diretoria decidiu não renovar o contrato "
                              "quando ele vencer em dezembro.", {ALERT}),
]

HAPPY_TURNS = [
    "Bom dia! O relatório semanal chegou certinho, obrigado.",
    "Que bom! Qualquer coisa estamos à disposição.",
    "O novo filtro por bairro ajudou muito a organizar as entregas.",
    "Ficamos felizes! Ele foi pedido por vários clientes.",
]
ANGRY_TURNS = [
    "De novo o sistema fora do ar no meio do almoço! Inaceitável.",
    "Pedimos desculpas, estamos atuando na instabilidade.",
    "Perdi 30 pedidos hoje por causa de vocês.",
    "Lamentamos muito, vamos analisar uma compensação.",
]


class ChurnRiskExample(Example):
    number = 5
    slug = "risco-churn"
    title = "Detecção de intenção de cancelamento (churn)"
    summary = ("Dá uma nota de risco de churn a cada nova mensagem de chat e alerta o Sucesso do Cliente "
               "assim que o risco fica alto.")

    def scenarios(self) -> list[Scenario]:
        conversation: list[dict] = []
        rounds = []
        for number, (reply, message, expected) in enumerate(ROUNDS, start=1):
            if reply:
                conversation.append({"autor": "suporte", "texto": reply})
            conversation.append({"autor": "cliente", "texto": message})
            rounds.append(self._evaluate(f"Rodada {number}", list(conversation), message, {expected}))

        standalone = [self._evaluate(label, [{"autor": "cliente", "texto": text}], text, accepted)
                      for label, text, accepted in STANDALONE]
        return [
            Scenario(
                title="Conversa que piora a cada rodada",
                description="A mesma conversa é reavaliada a cada nova mensagem do cliente (5 rodadas).",
                cases=rounds,
                metrics=_trend(rounds),
            ),
            Scenario(
                title="Mensagens avulsas",
                description="Mensagens independentes com intenção clara.",
                cases=standalone,
                metrics=_trend(standalone),
            ),
        ]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [self._evaluate(label, [{"autor": "cliente", "texto": text}], text, accepted)
                  for label, text, accepted in TRICKY]
        long_history = [
            self._evaluate(
                "Meses de elogios + pedido de cancelamento",
                _turns(HAPPY_TURNS, rounds=12) + [{"autor": "cliente", "texto": "Chega. Quero cancelar tudo hoje."}],
                f"{len(HAPPY_TURNS) * 12} mensagens positivas; última: 'Chega. Quero cancelar tudo hoje.'",
                {ALERT},
            ),
            self._evaluate(
                "Meses de reclamações + problema resolvido",
                _turns(ANGRY_TURNS, rounds=12) + [{"autor": "cliente", "texto": "Problema resolvido de vez, obrigado! "
                                                                                "Vocês salvaram nosso fim de semana."}],
                f"{len(ANGRY_TURNS) * 12} mensagens de reclamação; última: 'Problema resolvido de vez, obrigado!'",
                {NO_ACTION, WATCH},
            ),
        ]
        return [
            Scenario(
                title="Linguagem enganosa",
                description="Sarcasmo, 'cancelar' com outro sentido, sinais indiretos de saída e recusa educada.",
                bonus=True,
                stress="Separar a palavra 'cancelar' da intenção de churn e captar sinais implícitos.",
                cases=tricky,
                metrics=_trend(tricky),
            ),
            Scenario(
                title="Histórico longo com virada na última mensagem",
                description="A mensagem mais recente contradiz meses de histórico.",
                bonus=True,
                stress="State grande: a virada fica no fim e o histórico antigo puxa a nota para o lado oposto.",
                cases=long_history,
                metrics=_trend(long_history),
            ),
        ]

    def _evaluate(self, label: str, conversation: list[dict], summary: str, accepted: set[str]) -> Case:
        expected = " ou ".join(sorted(accepted))
        call = self._ask({"cliente": CLIENT, "conversa": conversation}, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)

        risk = call.score("risco_churn")
        cancel_request = call.noul("pedido_cancelamento")
        competitor = call.noul("cita_concorrente")
        if cancel_request >= 0.7 or risk.score >= 3.0:
            action = ALERT
        elif risk.score >= 1.8 or competitor >= 0.6:
            action = WATCH
        else:
            action = NO_ACTION
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=action,
            expected=expected,
            passed=action in accepted,
            details={
                "churn score (0-100)": round(normalized(risk) * 100),
                "nível de risco (0-4)": round(risk.score, 2),
                "pedido explícito": round(cancel_request, 3),
                "cita concorrente": round(competitor, 3),
                "regras": "pedido ≥ 0,7 ou nível ≥ 3 → alerta; nível ≥ 1,8 ou concorrente ≥ 0,6 → monitorar",
            },
        )


def _turns(turns: list[str], rounds: int) -> list[dict]:
    return [{"autor": "cliente" if position % 2 == 0 else "suporte", "texto": text}
            for _ in range(rounds) for position, text in enumerate(turns)]


def _trend(cases: list[Case]) -> dict:
    scores = [case.details["churn score (0-100)"] for case in cases if case.error is None]
    return {"churn score por caso": " → ".join(str(score) for score in scores)} if scores else {}
