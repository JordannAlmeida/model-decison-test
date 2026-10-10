"""10. Análise de sentimento e feedback em massa.

Um lote de avaliações é processado em paralelo. Para cada uma, o modelo de decisão dá uma nota
de insatisfação de 1 a 5 (Score com níveis descritos por situações) e o tema principal (Choice).
O código ordena o lote para que o time priorize os clientes mais insatisfeitos.
"""

from examples.base import Example
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, ScoreQuestion, Type

TOLERANCE = 0.75  # how far the 1..5 grade may be from the expected one
PRIORITY_FROM = 4.0

QUESTIONS = {
    "insatisfacao": ScoreQuestion(
        type=Type.SCORE,
        instructions="Qual o nível de insatisfação do cliente nesta `avaliacao`?",
        criteria=[
            "Elogio ou satisfação clara; nenhuma reclamação",
            "Satisfeito no geral, com uma ressalva leve",
            "Experiência mista: pontos positivos e negativos equivalentes",
            "Insatisfeito: problema relevante que não foi resolvido",
            "Muito insatisfeito: revolta, pede reembolso, ameaça reclamar em órgãos ou promete nunca mais comprar",
        ],
    ),
    "tema": ChoiceQuestion(
        type=Type.CHOICE,
        instructions="Qual é o tema principal da `avaliacao`?",
        criteria={
            "entrega": "Prazo, atraso, extravio ou condição da entrega",
            "produto": "Qualidade, defeito, tamanho ou descrição do produto",
            "atendimento": "Contato com o SAC, chat ou vendedores",
            "preco": "Preço, cobrança, frete ou descontos",
            "app_site": "Uso do aplicativo ou do site",
            "outro": None,
        },
    ),
}

REGULAR = [
    ("Produto excelente, chegou antes do prazo e muito bem embalado. Recomendo!", 1),
    ("Gostei bastante, só achei a caixa meio amassada, mas o produto está perfeito.", 2),
    ("O produto é bom, mas demorou demais para chegar e ninguém avisava nada.", 3),
    ("Veio a cor errada e até agora não consegui trocar. Muito chato.", 4),
    ("PÉSSIMO! Produto quebrado, o atendimento me ignorou e quero meu dinheiro de volta. Nunca mais compro aqui.", 5),
    ("Atendimento nota 10, a Juliana resolveu meu problema em minutos.", 1),
    ("Preço justo, qualidade ok. Nada de especial.", 2),
    ("O app trava toda vez que tento finalizar a compra. Já desisti duas vezes.", 4),
    ("Cobraram o frete duas vezes e o SAC disse que não pode fazer nada. Absurdo, vou no Procon.", 5),
    ("Entrega rápida, mas o tamanho veio menor do que a tabela indicava.", 3),
    ("Comprei pela terceira vez, sempre tudo certo. Loja de confiança.", 1),
    ("Demorou 20 dias, mas chegou certinho.", 2),
]

TRICKY = [
    ("Amei esperar 40 dias pela entrega. Nota 10 pela paciência que desenvolvi.", 4),
    ("pqp q lixo, chegou tudo quebrado 🤬🤬🤬", 5),
    ("top demais 👏👏 chegou rapidão", 1),
    ("The product is ok mas a entrega foi um desastre, o segundo volume nunca chegou.", 4),
    ("Atendimento simpático, embalagem linda, cheirinho bom... pena que o produto veio vencido.", 4),
    ("Não posso dizer que não gostei.", 2),
]

PRAISE = [
    "Quero começar dizendo que a experiência de compra foi muito agradável: o site é bonito, rápido e fácil "
    "de navegar, e encontrei tudo o que procurava em poucos minutos.",
    "O processo de pagamento foi simples, aceitaram meu cartão sem problemas e recebi a confirmação por "
    "e-mail na hora, com todos os detalhes do pedido bem organizados.",
    "A embalagem chegou impecável, com plástico bolha, papel de seda e até um bilhetinho escrito à mão "
    "agradecendo pela compra, o que achei um carinho muito especial.",
    "O entregador foi educado, chegou no horário combinado e ainda esperou eu descer para conferir a caixa.",
]
SERIOUS_COMPLAINT = ("Porém, ao comparar com o produto da loja oficial, descobri que o que recebi é falsificado: "
                     "o número de série não existe no site do fabricante. Quero reembolso imediato e já registrei "
                     "reclamação no Procon.")


class SentimentBatchExample(Example):
    number = 10
    slug = "sentimento-massa"
    title = "Análise de sentimento e feedback em massa"
    summary = ("Processa um lote de avaliações em paralelo, dá a cada uma uma nota de insatisfação de 1 a 5 e "
               "ordena o lote para priorizar os clientes mais insatisfeitos.")

    def scenarios(self) -> list[Scenario]:
        return [self._batch("Lote de avaliações da semana", "Avaliações curtas de um e-commerce, das mais "
                            "elogiosas às mais revoltadas.", REGULAR)]

    def bonus_scenarios(self) -> list[Scenario]:
        praise = " ".join(PRAISE * 9)
        long_reviews = [(praise + " " + SERIOUS_COMPLAINT, 5), (praise, 1)]
        return [
            self._batch("Linguagem difícil", "Sarcasmo, palavrão, emojis, gírias, mistura de idiomas e dupla "
                        "negação.", TRICKY,
                        stress="Ler a intenção real por trás de ironia, abreviações e emojis."),
            self._batch("Avaliação longa", "Uma avaliação extensa só de elogios, com e sem uma denúncia grave "
                        "no último parágrafo.", long_reviews,
                        stress="State grande: a reclamação grave fica no fim e pode ser truncada.",
                        labels=["Elogios + denúncia de falsificação no fim", "Só elogios (controle)"]),
        ]

    def _batch(self, title: str, description: str, reviews: list[tuple[str, int]], stress: str | None = None,
               labels: list[str] | None = None) -> Scenario:
        labels = labels or [f"Avaliação {index:02d}" for index in range(1, len(reviews) + 1)]
        states = [{"canal": "app", "avaliacao": text} for text, _ in reviews]
        calls = self._ask_each(states, QUESTIONS, labels)

        cases = []
        for label, call, (text, expected) in zip(labels, calls, reviews, strict=True):
            summary = text if len(text) < 300 else f"{text[:120]} (…) {text[-160:]}"
            if call.failed:
                cases.append(Case.from_failure(label, [call], f"nota {expected}", summary))
                continue
            grade = 1 + call.score("insatisfacao").score
            topic = call.choice("tema")
            cases.append(Case(
                label=label,
                input_summary=summary,
                calls=[call],
                outcome=f"nota {grade:.1f}",
                expected=f"nota {expected} (±{TOLERANCE})",
                passed=abs(grade - expected) <= TOLERANCE,
                details={"nota (1-5)": round(grade, 2), "tema": topic.choice,
                         "P(tema)": round(topic.probabilities[topic.choice], 2)},
            ))
        return Scenario(title=title, description=description, bonus=stress is not None, stress=stress,
                        cases=cases, metrics=_summary(cases))


def _summary(cases: list[Case]) -> dict:
    graded = [case for case in cases if case.error is None]
    if not graded:
        return {}
    grades = [case.details["nota (1-5)"] for case in graded]
    histogram = {str(level): sum(1 for grade in grades if round(grade) == level) for level in range(1, 6)}
    worst = sorted(graded, key=lambda case: case.details["nota (1-5)"], reverse=True)
    topics = [case.details["tema"] for case in graded if case.details["nota (1-5)"] >= PRIORITY_FROM]
    return {
        "nota média": round(sum(grades) / len(grades), 2),
        "distribuição (nota arredondada)": histogram,
        "fila de prioridade (mais insatisfeitos)": ", ".join(case.label for case in worst[:3]),
        f"tema mais comum entre notas ≥ {PRIORITY_FROM:.0f}": max(set(topics), key=topics.count) if topics else "—",
    }
