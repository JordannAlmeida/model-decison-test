"""7. Triagem e roteamento de suporte ao cliente.

Na mesma chamada, o modelo de decisão escolhe o setor (Choice) e dá a prioridade (Score de
quatro níveis descritos por impacto). O código escolhe a fila, o SLA e se outro setor deve ser
copiado.
"""

from examples.base import Example, ranked
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, ScoreQuestion, Type

MANUAL = "triagem_manual"
MIN_TOP_PROBABILITY = 0.45
COPY_PROBABILITY = 0.25
PRIORITIES = ["baixa", "média", "alta", "crítica"]
SLA = {"baixa": "72h", "média": "24h", "alta": "4h", "crítica": "1h"}

SECTOR = ChoiceQuestion(
    type=Type.CHOICE,
    instructions="Qual setor deve atender este chamado?",
    criteria={
        "tecnico": {
            "o_que": "Erros, falhas, lentidão, acesso, integrações e dúvidas de uso do sistema",
            "nao_inclui": "Cobranças e notas fiscais (financeiro)",
        },
        "financeiro": {
            "o_que": "Cobranças, faturas, boletos, notas fiscais, estornos e dados de pagamento",
            "nao_inclui": "Contratação ou mudança de plano (vendas)",
        },
        "vendas": "Contratação, upgrade ou downgrade de plano, propostas e preços de novos produtos",
        "outro": "Assuntos que não são de nenhum dos setores acima",
    },
)
PRIORITY = ScoreQuestion(
    type=Type.SCORE,
    instructions="Qual é o impacto do problema relatado no chamado?",
    criteria=[
        "Dúvida, sugestão ou pedido de informação; nada está quebrado",
        "Problema que incomoda, mas não impede o trabalho; há contorno ou pode esperar alguns dias",
        "Impede o trabalho de um usuário ou equipe, ou causa prejuízo financeiro a um cliente, sem contorno",
        "Indisponibilidade geral, perda ou vazamento de dados, ou prejuízo para muitos clientes",
    ],
)
QUESTIONS = {"setor": SECTOR, "prioridade": PRIORITY}

SUBQUEUES = {
    "tecnico/login": "Acesso, senha, bloqueio de conta e autenticação em dois fatores",
    "tecnico/api": "Erros e limites da API pública e de webhooks",
    "tecnico/relatorios": "Relatórios e exportações com erro ou valores incorretos",
    "tecnico/integracao-erp": "Sincronização com ERPs e sistemas contábeis",
    "tecnico/app-mobile": "Falhas no aplicativo para celular",
    "tecnico/desempenho": "Lentidão e indisponibilidade do sistema",
    "tecnico/seguranca": "Vazamento de dados, acesso indevido e vulnerabilidades",
    "tecnico/ponto-eletronico": "Registro de ponto e banco de horas",
    "tecnico/estoque": "Movimentação e contagem de estoque",
    "tecnico/pdv": "Frente de caixa e emissão de cupom no ponto de venda",
    "tecnico/notificacoes": "E-mails, SMS e notificações que não chegam",
    "tecnico/perfil": "Dados cadastrais, foto e preferências do usuário",
    "financeiro/cobranca-duplicada": "Cobrança em duplicidade",
    "financeiro/nota-fiscal": "Emissão, correção e envio de notas fiscais",
    "financeiro/estorno": "Pedidos de estorno e reembolso",
    "financeiro/boleto": "Segunda via e vencimento de boletos",
    "financeiro/inadimplencia": "Bloqueio por falta de pagamento e negociação de débitos",
    "financeiro/reajuste": "Reajuste anual e mudança de preço",
    "financeiro/cartao": "Troca de cartão de crédito e falhas de pagamento",
    "vendas/upgrade": "Mudança para um plano superior",
    "vendas/downgrade": "Mudança para um plano inferior",
    "vendas/novo-contrato": "Contratação para nova empresa ou filial",
    "vendas/demonstracao": "Pedido de demonstração do produto",
    "vendas/parceria": "Revenda e parcerias comerciais",
    "vendas/desconto": "Negociação de desconto e condições especiais",
    "vendas/modulos": "Contratação de módulos adicionais",
    "outro/imprensa": "Contato de jornalistas",
    "outro/vagas": "Currículos e vagas de emprego",
    "outro/juridico": "Notificações judiciais e LGPD",
    "outro/elogio": "Elogios e agradecimentos",
}
SUBQUEUE_QUESTION = ChoiceQuestion(
    type=Type.CHOICE,
    instructions="Para qual subfila este chamado deve ir?",
    criteria=SUBQUEUES,
)

REGULAR = [
    ("Sem acesso antes de prazo", "Não consigo acessar minha conta desde a manhã; aparece 'senha inválida' mesmo "
     "depois de redefinir. Preciso fechar o relatório do mês hoje.", {"tecnico"}, "alta"),
    ("Cobrança duplicada", "Fui cobrado duas vezes na fatura de outubro. Podem estornar uma das cobranças?",
     {"financeiro"}, "alta"),
    ("Dúvida de plano", "Gostaria de saber se o plano Profissional inclui integração com ERP e quanto custa para "
     "50 usuários.", {"vendas"}, "baixa"),
    ("Sistema fora do ar", "O sistema inteiro está fora do ar para todos da empresa, erro 503 em todas as telas.",
     {"tecnico"}, "crítica"),
    ("Troca de e-mail de NF", "Como altero o e-mail que recebe as notas fiscais?", {"financeiro"}, "baixa"),
    ("Relatório com contorno", "O relatório de vendas está mostrando os valores com uma casa decimal a menos, mas "
     "consigo exportar o CSV e corrigir manualmente.", {"tecnico"}, "média"),
]

TRICKY = [
    ("Urgência falsa", "URGENTE!!!!!! COMO TROCO A FOTO DO MEU PERFIL???", {"tecnico"}, "baixa"),
    ("Urgência silenciosa", "Olá, tudo bem? Sem pressa: notamos que desde ontem nenhum dos nossos 300 funcionários "
     "consegue registrar o ponto no sistema. Quando puderem, deem uma olhada.", {"tecnico"}, "crítica"),
    ("Bug que gera cobrança", "Depois da atualização de ontem, o sistema gerou boletos em duplicidade para todos "
     "os nossos clientes.", {"tecnico", "financeiro"}, "crítica"),
    ("Vazamento de dados", "Ao exportar o relatório de folha, recebi uma planilha com CPF e salário de funcionários "
     "de outra empresa.", {"tecnico"}, "crítica"),
]

SUBQUEUE_CASES = [
    ("Subfila: ponto eletrônico", TRICKY[1][1], "tecnico/ponto-eletronico"),
    ("Subfila: segurança", TRICKY[3][1], "tecnico/seguranca"),
    ("Subfila: nota fiscal", REGULAR[4][1], "financeiro/nota-fiscal"),
    ("Subfila: upgrade", "Quero passar do plano Básico para o Profissional ainda este mês.", "vendas/upgrade"),
    ("Subfila: perfil", TRICKY[0][1], "tecnico/perfil"),
]

LOG_LINE = ("2026-10-09T12:{minute:02d}:{second:02d}Z ERROR [pdv-sync] worker-{worker} "
            "TimeoutException: sync batch {batch} exceeded 30000ms at br.loja.pdv.SyncService.flush(SyncService.java:{line})")


class SupportTriageExample(Example):
    number = 7
    slug = "triagem-suporte"
    title = "Triagem e roteamento de suporte ao cliente"
    summary = ("Lê o chamado e decide na hora o setor (técnico, financeiro ou vendas) e a prioridade, "
               "direcionando para a fila e o SLA corretos.")

    def scenarios(self) -> list[Scenario]:
        cases = [self._triage(label, {"mensagem": text}, text, sectors, priority)
                 for label, text, sectors, priority in REGULAR]
        return [Scenario(
            title="Chamados do dia",
            description="Chamados com setor e impacto bem definidos.",
            cases=cases,
            metrics=_queues(cases),
        )]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [self._triage(label, {"mensagem": text}, text, sectors, priority)
                  for label, text, sectors, priority in TRICKY]
        subqueues = [self._subqueue(label, text, expected) for label, text, expected in SUBQUEUE_CASES]
        log = _log(lines=45)
        logs = [
            self._triage("Log extenso, impacto no início",
                         {"mensagem": "O fechamento de caixa trava em todas as nossas 40 lojas desde as 12h. Segue o log:",
                          "log": log},
                         "Fechamento de caixa travado em 40 lojas (na primeira linha) + 45 linhas de log",
                         {"tecnico"}, "crítica"),
            self._triage("Log extenso, impacto no fim",
                         {"log": log,
                          "mensagem": "Esse é o log do fechamento de caixa. Isso está acontecendo em todas as nossas "
                                      "40 lojas desde as 12h."},
                         "45 linhas de log + 'acontecendo em todas as 40 lojas' na última linha",
                         {"tecnico"}, "crítica"),
        ]
        return [
            Scenario(
                title="Sinais enganosos de urgência e de setor",
                description="Caixa alta sem impacto, impacto enorme em tom calmo, bug que vira cobrança e vazamento.",
                bonus=True,
                stress="Separar tom da mensagem de impacto real e lidar com chamados de dois setores.",
                cases=tricky,
                metrics=_queues(tricky),
            ),
            Scenario(
                title=f"Taxonomia com {len(SUBQUEUES)} subfilas",
                description="Um único Choice com todas as subfilas de todos os setores.",
                bonus=True,
                stress="Muitas opções num Choice; o Laya divide um orçamento de tokens entre elas.",
                cases=subqueues,
            ),
            Scenario(
                title="Chamado com log extenso",
                description="O mesmo log longo, com a frase que define o impacto antes ou depois dele.",
                bonus=True,
                stress="State grande: a informação que define a prioridade pode ser truncada.",
                cases=logs,
                metrics=_queues(logs),
            ),
        ]

    def _triage(self, label: str, state: dict, summary: str, sectors: set[str], priority: str) -> Case:
        expected = f"{' ou '.join(sorted(sectors))} · {priority}"
        call = self._ask(state, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)

        options = ranked(call.choice("setor"))
        (top, top_p), (second, second_p) = options[0], options[1]
        sector = top if top_p >= MIN_TOP_PROBABILITY else MANUAL
        score = call.score("prioridade").score
        level = PRIORITIES[min(round(score), len(PRIORITIES) - 1)]
        copy = second if sector != MANUAL and second_p >= COPY_PROBABILITY else None
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=f"{sector} · {level}",
            expected=expected,
            passed=sector in sectors and level == priority,
            details={
                "fila": sector if sector != MANUAL else "triagem manual (modelo indeciso)",
                "SLA": SLA[level],
                "cópia para": copy or "—",
                "setor (1ª / 2ª)": f"{top} {top_p:.2f} / {second} {second_p:.2f}",
                "prioridade (0-3)": round(score, 2),
            },
        )

    def _subqueue(self, label: str, text: str, expected: str) -> Case:
        call = self._ask({"mensagem": text}, {"subfila": SUBQUEUE_QUESTION}, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, text)
        options = ranked(call.choice("subfila"))
        position = next(index for index, (option, _) in enumerate(options, start=1) if option == expected)
        return Case(
            label=label,
            input_summary=text,
            calls=[call],
            outcome=options[0][0],
            expected=expected,
            passed=options[0][0] == expected,
            details={
                "top-3": ", ".join(f"{option} ({p:.2f})" for option, p in options[:3]),
                "posição da subfila esperada": f"{position}º de {len(options)}",
            },
        )


def _log(lines: int) -> str:
    return "\n".join(LOG_LINE.format(minute=index // 6, second=(index * 7) % 60, worker=index % 4,
                                     batch=1000 + index, line=200 + index % 9)
                     for index in range(lines))


def _queues(cases: list[Case]) -> dict:
    outcomes = [case.outcome for case in cases if case.error is None]
    return {outcome: outcomes.count(outcome) for outcome in sorted(set(outcomes))}
