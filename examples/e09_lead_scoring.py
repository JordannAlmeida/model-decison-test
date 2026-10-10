"""9. Qualificação e pontuação de leads (lead scoring).

O modelo de decisão lê o registro do lead no CRM de uma construtora e escolhe o estágio
(Choice). Na mesma chamada, três fatores (dois Scores e um Noul) formam uma pontuação 0-100
para ordenar a carteira, servindo também de reserva quando o Choice fica indeciso.
"""

from examples.base import Example, normalized, ranked
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, NoulQuestion, ScoreQuestion, Type

READY = "pronto_para_fechamento"
NURTURE = "necessita_nutricao"
COLD = "lead_frio"
MIN_TOP_PROBABILITY = 0.5
WEIGHTS = {"fit": 0.25, "engajamento": 0.45, "capacidade_de_compra": 0.30}

QUESTIONS = {
    "estagio": ChoiceQuestion(
        type=Type.CHOICE,
        instructions="Em que estágio de compra está este lead de um empreendimento imobiliário?",
        criteria={
            READY: "Intenção concreta: pediu proposta ou contrato, tem crédito aprovado ou entrada definida",
            NURTURE: "Interesse real, mas ainda pesquisa, compara opções ou não tem crédito ou entrada",
            COLD: "Sem interação recente, sem interesse demonstrado ou fora do perfil do empreendimento",
        },
    ),
    "fit": ScoreQuestion(
        type=Type.SCORE,
        instructions="O perfil do lead combina com o `empreendimento`?",
        criteria=[
            "Fora do perfil: renda, região ou necessidade não combinam com o empreendimento",
            "Perfil parcialmente compatível",
            "Perfil totalmente compatível com o empreendimento",
        ],
    ),
    "engajamento": ScoreQuestion(
        type=Type.SCORE,
        instructions="Qual o nível de engajamento do lead nas `interacoes` mais recentes?",
        criteria=[
            "Nenhuma interação nos últimos 90 dias",
            "Interações passivas: abriu e-mails ou visitou o site",
            "Interações ativas: pediu informações, simulou financiamento ou visitou o decorado",
            "Interações decisivas: pediu proposta, negociou condições ou agendou assinatura",
        ],
    ),
    "capacidade_de_compra": NoulQuestion(
        type=Type.NOUL,
        instructions="O lead tem crédito aprovado, entrada disponível ou orçamento confirmado para a compra?",
    ),
}

PROJECT = {"nome": "Residencial Horizonte Azul", "tipo": "apartamentos de 2 quartos", "cidade": "Contagem/MG",
           "faixa_de_preco": "R$ 260 mil a R$ 320 mil", "renda_familiar_sugerida": "a partir de R$ 6 mil"}

REGULAR = [
    ("Ana: crédito aprovado e proposta",
     {"nome": "Ana Ribeiro", "idade": 34, "renda_familiar": "R$ 9.500", "cidade": "Contagem"},
     ["Visitou o decorado duas vezes", "Simulou financiamento: crédito pré-aprovado",
      "Pediu proposta com entrada de R$ 40 mil e perguntou a data de assinatura"],
     "Quer fechar antes do fim do mês.", {READY}),
    ("Bruno: juntando a entrada",
     {"nome": "Bruno Costa", "idade": 27, "renda_familiar": "R$ 6.800", "cidade": "Belo Horizonte"},
     ["Baixou o e-book 'Primeiro imóvel'", "Abriu 3 e-mails da campanha", "Perguntou no chat a metragem da planta"],
     "Ainda juntando a entrada; prevê comprar em 2027.", {NURTURE}),
    ("Carla: sumida há 10 meses",
     {"nome": "Carla Mendes", "idade": 45, "renda_familiar": "não informada", "cidade": "Betim"},
     ["Cadastro no site há 10 meses", "Nenhuma abertura de e-mail desde então", "Telefone não atende"],
     "—", {COLD}),
    ("Daniel: contrato com o advogado",
     {"nome": "Daniel Souza", "idade": 38, "renda_familiar": "R$ 12.000", "cidade": "Contagem"},
     ["Financiamento e uso do FGTS aprovados", "Ligou pedindo a minuta do contrato para revisar com o advogado"],
     "Escolheu a unidade 804.", {READY}),
    ("Elisa: comparando empreendimentos",
     {"nome": "Elisa Prado", "idade": 31, "renda_familiar": "R$ 8.000", "cidade": "Contagem"},
     ["Visitou o site 5 vezes na última semana", "Pediu a tabela de preços",
      "Disse que está comparando com outros dois empreendimentos"],
     "Ainda não iniciou a análise de crédito.", {NURTURE}),
]

TRICKY = [
    ("Muito engajado, mas fora do perfil",
     {"nome": "Felipe Araújo", "idade": 21, "ocupacao": "estudante", "renda_familiar": "R$ 1.500"},
     ["Abriu todos os e-mails dos últimos 6 meses", "Visitou o decorado com a turma da faculdade",
      "Pediu dados de vendas para o TCC sobre mercado imobiliário"],
     "Não pretende comprar; pesquisa acadêmica.", {COLD}),
    ("Quente e silencioso",
     {"nome": "Gustavo Lima", "idade": 52, "renda_familiar": "R$ 25.000", "cidade": "Contagem"},
     ["Única interação: ligou dizendo que o crédito foi aprovado e quer assinar o contrato da unidade 1204 "
      "na semana que vem"],
     "—", {READY}),
    ("Engajado que desistiu",
     {"nome": "Helena Duarte", "idade": 36, "renda_familiar": "R$ 10.000", "cidade": "Contagem"},
     ["Visitou o decorado três vezes", "Simulou financiamento", "Negociou condições de entrada",
      "Mensagem mais recente: 'Agradecemos, mas decidimos comprar um imóvel de outra construtora.'"],
     "—", {COLD}),
    ("Pressa sem capacidade de compra",
     {"nome": "Igor Martins", "idade": 29, "renda_familiar": "R$ 3.200", "cidade": "Contagem"},
     ["Escreveu: 'Quero fechar HOJE!!!'", "Crédito negado duas vezes pelo banco", "Sem valor de entrada"],
     "Precisa reorganizar a renda antes de nova análise.", {NURTURE}),
]


class LeadScoringExample(Example):
    number = 9
    slug = "lead-scoring"
    title = "Qualificação e pontuação de leads (lead scoring)"
    summary = ("Avalia o registro de cada lead no CRM e decide se está pronto para fechamento, se precisa de "
               "nutrição ou se é um lead frio, com uma pontuação 0-100 para ordenar a carteira.")

    def scenarios(self) -> list[Scenario]:
        cases = [self._qualify(label, lead, events, notes, accepted)
                 for label, lead, events, notes, accepted in REGULAR]
        return [Scenario(
            title="Carteira de leads de um lançamento",
            description="Leads com sinais claros de cada estágio.",
            cases=cases,
            metrics=_ranking(cases),
        )]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [self._qualify(label, lead, events, notes, accepted)
                  for label, lead, events, notes, accepted in TRICKY]
        passive = [f"{month:02d}/2025: abriu a newsletter mensal" for month in range(1, 13)] + \
                  [f"{month:02d}/2026: visitou o blog e curtiu um post" for month in range(1, 10)]
        history = passive * 4 + ["10/2026: pediu a minuta do contrato da unidade 302 e enviou a carta de crédito aprovada"]
        long_history = [
            self._qualify("Anos de interações passivas + pedido de contrato no fim",
                          {"nome": "Júlia Fernandes", "idade": 40, "renda_familiar": "R$ 11.000", "cidade": "Contagem"},
                          history, "—", {READY},
                          summary=f"{len(history) - 1} interações passivas + pedido de contrato na última"),
        ]
        return [
            Scenario(
                title="Sinais contraditórios",
                description="Engajamento alto sem perfil, uma única interação decisiva, desistência depois de muito "
                            "engajamento e pressa sem crédito.",
                bonus=True,
                stress="Não confundir volume de interações com intenção e capacidade reais de compra.",
                cases=tricky,
                metrics=_ranking(tricky),
            ),
            Scenario(
                title="Histórico de interações extenso",
                description="Dezenas de interações passivas antes do evento que muda o estágio do lead.",
                bonus=True,
                stress="State grande: o evento decisivo é o último da lista e pode ser truncado.",
                cases=long_history,
                metrics=_ranking(long_history),
            ),
        ]

    def _qualify(self, label: str, lead: dict, events: list[str], notes: str, accepted: set[str],
                 summary: str | None = None) -> Case:
        expected = " ou ".join(sorted(accepted))
        summary = summary or " · ".join(events)
        state = {"empreendimento": PROJECT, "lead": lead, "interacoes": events, "notas_do_corretor": notes}
        call = self._ask(state, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)

        factors = {
            "fit": normalized(call.score("fit")),
            "engajamento": normalized(call.score("engajamento")),
            "capacidade_de_compra": call.noul("capacidade_de_compra"),
        }
        lead_score = sum(WEIGHTS[name] * value for name, value in factors.items())
        bucket = READY if lead_score >= 0.7 else NURTURE if lead_score >= 0.4 else COLD
        (top, top_p), (second, second_p) = ranked(call.choice("estagio"))[:2]
        stage = top if top_p >= MIN_TOP_PROBABILITY else bucket
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=stage,
            expected=expected,
            passed=stage in accepted,
            details={
                "lead score (0-100)": round(lead_score * 100),
                "estágio pelo Choice": f"{top} ({top_p:.2f}); 2º {second} ({second_p:.2f})",
                "estágio pela pontuação": bucket,
                "decidido por": "Choice" if stage == top and top_p >= MIN_TOP_PROBABILITY else "pontuação (Choice indeciso)",
                **{f"fator: {name}": round(value, 3) for name, value in factors.items()},
            },
        )


def _ranking(cases: list[Case]) -> dict:
    scored = sorted((case for case in cases if case.error is None),
                    key=lambda case: case.details["lead score (0-100)"], reverse=True)
    return {"carteira ordenada por lead score":
            " > ".join(f"{case.label.split(':')[0]} ({case.details['lead score (0-100)']})" for case in scored)}
