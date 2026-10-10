"""2. Avaliação da qualidade da resposta de agentes (LLM-as-a-Judge).

Antes de exibir a resposta de um agente, o modelo de decisão a avalia contra a fonte oficial:
clareza e precisão (Score), alucinação e se resolve a pergunta (Noul). O código combina as
notas e decide entre aprovar, devolver ao agente ou encaminhar a um operador humano.
"""

from examples.base import Example, normalized
from execution.results import Case, Scenario
from modelDecision.scheme import NoulCriteria, NoulQuestion, ScoreQuestion, Type

APPROVE = "aprovar e exibir ao usuário"
REVISE = "devolver ao agente para ajuste"
HUMAN = "encaminhar a operador humano"
HALLUCINATION_THRESHOLD = 0.5
QUALITY_THRESHOLD = 0.7

POLICY = [
    "Trocas e devoluções podem ser solicitadas em até 30 dias corridos após o recebimento.",
    "O reembolso é feito na mesma forma de pagamento em até 10 dias úteis após o produto chegar ao centro de distribuição.",
    "Produtos personalizados (com nome ou foto gravados) não podem ser trocados, exceto por defeito de fabricação.",
    "O frete da devolução é gratuito apenas quando o produto tem defeito; nos demais casos o cliente paga o frete.",
    "Para solicitar, o cliente acessa Meus Pedidos > Solicitar troca e imprime a etiqueta de postagem.",
]

QUESTIONS = {
    "clareza": ScoreQuestion(
        type=Type.SCORE,
        instructions="Quão clara é a `resposta_do_agente` para quem fez a pergunta?",
        criteria=[
            "Confusa ou contraditória; o usuário não saberia o que fazer",
            "Compreensível, mas prolixa, desorganizada ou cheia de rodeios",
            "Clara, direta e fácil de seguir",
        ],
    ),
    "precisao": ScoreQuestion(
        type=Type.SCORE,
        instructions="A `resposta_do_agente` está de acordo com a `fonte_oficial`?",
        criteria=[
            "Contradiz a `fonte_oficial` em um ponto importante",
            "Parcialmente correta: omite ou distorce um detalhe relevante",
            "Totalmente consistente com a `fonte_oficial`",
        ],
    ),
    "alucinacao": NoulQuestion(
        type=Type.NOUL,
        instructions="A `resposta_do_agente` afirma algum prazo, valor, benefício ou regra que não está na `fonte_oficial`?",
        criteria=NoulCriteria(
            true="Inventa ou altera informação: prazo, percentual, cupom, brinde ou regra ausente da fonte",
            false="Tudo o que afirma está na fonte ou é apenas cortesia neutra",
        ),
    ),
    "resolve": NoulQuestion(
        type=Type.NOUL,
        instructions="A `resposta_do_agente` responde diretamente ao que a `pergunta_do_usuario` pede?",
    ),
}

SIZE_QUESTION = "Comprei um tênis há 12 dias e não serviu. Posso trocar?"
REFUND_QUESTION = "Em quanto tempo recebo o reembolso depois de devolver?"
MUG_QUESTION = "Comprei uma caneca com a foto do meu cachorro e me arrependi. Posso devolver?"

REGULAR = [
    ("Resposta correta e completa", SIZE_QUESTION,
     "Pode sim! Você tem até 30 dias corridos após o recebimento. Acesse Meus Pedidos > Solicitar troca e "
     "imprima a etiqueta. Como não é defeito, o frete da devolução fica por sua conta.",
     {APPROVE}),
    ("Alucinação grosseira", SIZE_QUESTION,
     "Claro! Você tem 90 dias para trocar, o frete é sempre grátis e ainda ganha um cupom de 20% na próxima compra.",
     {HUMAN}),
    ("Correta, mas confusa", SIZE_QUESTION,
     "Então, depende, porque tem prazo, mas o prazo é contado de um jeito, e tem a questão do frete que às vezes "
     "é e às vezes não é, e se for personalizado é outra coisa, mas talvez dê, vê lá no site em algum lugar.",
     {REVISE}),
    ("Não responde à pergunta", REFUND_QUESTION,
     "Nossos produtos são enviados em até 2 dias úteis e você pode acompanhar a entrega pelo aplicativo.",
     {REVISE}),
    ("Reembolso correto", REFUND_QUESTION,
     "O reembolso é feito na mesma forma de pagamento em até 10 dias úteis depois que o produto chega ao nosso "
     "centro de distribuição.",
     {APPROVE}),
]

SUBTLE = [
    ("Um número errado no meio de acertos", REFUND_QUESTION,
     "Assim que o produto chegar ao centro de distribuição, o reembolso é feito na mesma forma de pagamento "
     "em até 15 dias úteis. Você pode acompanhar tudo em Meus Pedidos.",
     {HUMAN, REVISE}),
    ("Omite a exceção do produto personalizado", MUG_QUESTION,
     "Pode sim! Você tem até 30 dias corridos para devolver; é só acessar Meus Pedidos > Solicitar troca.",
     {HUMAN, REVISE}),
    ("Recusa correta, citando a exceção", MUG_QUESTION,
     "Infelizmente produtos personalizados, como canecas com foto, não podem ser trocados, a não ser que "
     "apresentem defeito de fabricação.",
     {APPROVE}),
    ("Inventa uma alternativa 'simpática'", MUG_QUESTION,
     "Produtos personalizados não podem ser trocados, mas como compensação vamos te enviar um vale-presente "
     "de R$ 50 para usar no site.",
     {HUMAN, REVISE}),
]

FILLER_TOPICS = [
    "vale-presente", "programa de pontos", "entrega expressa", "retirada em loja", "garantia estendida",
    "pagamento via Pix", "parcelamento no cartão", "cupons promocionais", "pré-venda", "produtos de marketplace",
    "assinatura mensal", "atendimento por chat", "lista de casamento", "compras corporativas", "embalagem para presente",
    "avaliações de produtos", "cadastro e senha", "privacidade de dados", "notas fiscais", "entregas em condomínios",
]


class LlmAsJudgeExample(Example):
    number = 2
    slug = "llm-as-a-judge"
    title = "Avaliação de respostas de agentes (LLM-as-a-Judge)"
    summary = ("Avalia clareza, precisão e alucinação da resposta de um agente de atendimento antes de exibi-la; "
               "respostas abaixo do limiar voltam para ajuste ou vão para um operador humano.")

    def scenarios(self) -> list[Scenario]:
        cases = [self._judge(label, question, answer, POLICY, accepted)
                 for label, question, answer, accepted in REGULAR]
        return [Scenario(
            title="Respostas de um agente de trocas e devoluções",
            description="Política de trocas curta como fonte oficial; respostas boas, alucinadas, confusas e fora do tema.",
            cases=cases,
            metrics=_tally(cases),
        )]

    def bonus_scenarios(self) -> list[Scenario]:
        subtle = [self._judge(label, question, answer, POLICY, accepted)
                  for label, question, answer, accepted in SUBTLE]
        long_policy = _long_policy()
        long_source = [
            self._judge("Fonte longa: resposta correta", MUG_QUESTION,
                        "Produtos personalizados não podem ser trocados, exceto em caso de defeito de fabricação.",
                        long_policy, {APPROVE}),
            self._judge("Fonte longa: resposta alucinada", MUG_QUESTION,
                        "Pode devolver sim, em até 60 dias, e o frete de volta é por nossa conta.",
                        long_policy, {HUMAN, REVISE}),
        ]
        return [
            Scenario(
                title="Alucinações sutis",
                description="Respostas quase corretas: um número trocado, uma exceção omitida, um benefício inventado.",
                bonus=True,
                stress="Detectar um único detalhe falso no meio de informações verdadeiras.",
                cases=subtle,
                metrics=_tally(subtle),
            ),
            Scenario(
                title="Fonte oficial extensa",
                description=f"Política com {len(long_policy)} cláusulas; a regra de produtos personalizados é a última.",
                bonus=True,
                stress="State grande: a cláusula decisiva fica no fim da fonte e a resposta vem depois dela.",
                cases=long_source,
                metrics=_tally(long_source),
            ),
        ]

    def _judge(self, label: str, question: str, answer: str, source: list[str], accepted: set[str]) -> Case:
        state = {"pergunta_do_usuario": question, "fonte_oficial": source, "resposta_do_agente": answer}
        summary = f"Pergunta: {question}\nResposta do agente: {answer}"
        expected = " ou ".join(sorted(accepted))
        call = self._ask(state, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)

        clarity = normalized(call.score("clareza"))
        accuracy = normalized(call.score("precisao"))
        resolves = call.noul("resolve")
        hallucination = call.noul("alucinacao")
        quality = 0.25 * clarity + 0.5 * accuracy + 0.25 * resolves

        if hallucination >= HALLUCINATION_THRESHOLD:
            verdict = HUMAN
        elif quality >= QUALITY_THRESHOLD:
            verdict = APPROVE
        else:
            verdict = REVISE
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=verdict,
            expected=expected,
            passed=verdict in accepted,
            details={
                "clareza (0-1)": round(clarity, 3),
                "precisão (0-1)": round(accuracy, 3),
                "resolve a pergunta": round(resolves, 3),
                "alucinação": round(hallucination, 3),
                "nota de qualidade": round(quality, 3),
                "limiares": f"alucinação ≥ {HALLUCINATION_THRESHOLD} → humano; qualidade ≥ {QUALITY_THRESHOLD} → aprovar",
            },
        )


def _long_policy() -> list[str]:
    clauses = [
        f"{topic.capitalize()}: as regras de {topic} seguem o regulamento publicado na central de ajuda e podem "
        f"ser atualizadas sem aviso prévio. Dúvidas sobre {topic} devem ser enviadas pelo chat com o número do "
        f"pedido, e a resposta é dada em até dois dias úteis."
        for topic in FILLER_TOPICS
    ]
    return clauses + POLICY[:2] + POLICY[3:] + [POLICY[2]]


def _tally(cases: list[Case]) -> dict:
    verdicts = [case.outcome for case in cases]
    return {label: verdicts.count(label) for label in (APPROVE, REVISE, HUMAN)}
