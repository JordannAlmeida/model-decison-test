"""4. Classificação e triagem de tipos de e-mail.

O modelo de decisão lê remetente, assunto, corpo e anexos e escolhe uma categoria (Choice).
O código transforma a categoria na ação seguinte e, quando a segunda opção também é
provável, copia o setor correspondente.
"""

from examples.base import Example, ranked
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, Type

MANUAL = "triagem_manual"
MIN_TOP_PROBABILITY = 0.5
COPY_PROBABILITY = 0.25

ACTIONS = {
    "fatura_comprovante": "ler anexos automaticamente e conciliar no financeiro",
    "solicitacao_suporte": "abrir ticket no sistema de suporte",
    "proposta_comercial": "encaminhar ao time comercial",
    "spam_descarte": "descartar",
    "cancelamento": "acionar o time de retenção",
    "outro": "triagem manual",
    MANUAL: "triagem manual (modelo indeciso)",
}

QUESTIONS = {
    "categoria": ChoiceQuestion(
        type=Type.CHOICE,
        instructions="Qual é a categoria deste e-mail recebido na caixa de entrada da empresa?",
        criteria={
            "fatura_comprovante": {
                "o_que": "Envio de boleto, nota fiscal, fatura, recibo ou comprovante de pagamento",
                "nao_inclui": "Cobrança suspeita que pede para clicar em link e pagar com urgência (spam_descarte)",
            },
            "solicitacao_suporte": {
                "o_que": "Problema técnico, dúvida de uso ou reclamação sobre o serviço",
                "nao_inclui": "Pedido para encerrar contrato ou assinatura (cancelamento)",
            },
            "proposta_comercial": "Fornecedor oferecendo produto ou serviço, pedido de orçamento ou parceria",
            "spam_descarte": "Propaganda em massa não solicitada, phishing, golpe, sorteio ou corrente",
            "cancelamento": {
                "o_que": "Cliente pede para encerrar o contrato, o plano, a assinatura ou o serviço",
                "nao_inclui": "Cancelamento de reunião, pedido ou agendamento (outro)",
            },
            "outro": "Nenhuma das categorias acima, como avisos internos ou recados",
        },
    ),
}

REGULAR = [
    ("Comprovante de pagamento", "financeiro@clientex.com.br", "Comprovante de pagamento - NF 4521",
     "Olá, segue em anexo o comprovante de pagamento da nota fiscal 4521, referente a setembro. Att, Marcos.",
     ["comprovante_nf4521.pdf"], {"fatura_comprovante"}),
    ("Erro no sistema", "ana.souza@padariadourada.com.br", "Erro ao gerar relatório",
     "Bom dia, desde a atualização de ontem o botão 'Exportar relatório' retorna erro 500. Já limpei o cache e "
     "tentei em outro navegador. Podem verificar?",
     [], {"solicitacao_suporte"}),
    ("Proposta de fornecedor", "contato@nuvemsul.com.br", "Proposta de parceria - consultoria em nuvem",
     "Prezados, somos a NuvemSul e gostaríamos de apresentar nossa consultoria de migração para nuvem, com 20% "
     "de desconto no primeiro ano. Podemos agendar 30 minutos?",
     ["apresentacao_nuvemsul.pdf"], {"proposta_comercial"}),
    ("Sorteio falso", "premios@sorteio-mega.top", "VOCÊ GANHOU!!! Resgate seu prêmio",
     "Parabéns! Seu e-mail foi sorteado e você ganhou um iPhone. Clique no link e informe seus dados para receber.",
     [], {"spam_descarte"}),
    ("Pedido de cancelamento", "diretoria@lojasbeta.com.br", "Encerramento do contrato",
     "Olá, gostaríamos de cancelar nossa assinatura do plano Empresarial a partir do próximo mês. Por favor, "
     "confirmem os próximos passos.",
     [], {"cancelamento"}),
    ("Nota fiscal de fornecedor", "faturamento@manutencaototal.com.br", "NF-e 88123 - Serviços de outubro",
     "Segue a NF-e 88123 referente aos serviços de manutenção de outubro, com boleto para 15/11.",
     ["nfe_88123.xml", "boleto_88123.pdf"], {"fatura_comprovante"}),
]

TRICKY = [
    ("Phishing disfarçado de fatura", "cobranca@banco-segur0.xyz", "Fatura em atraso - regularize HOJE",
     "Identificamos uma fatura em aberto em seu nome. Para evitar o bloqueio do CPF, pague agora pelo link "
     "bit.ly/2via-fatura-urgente.",
     [], {"spam_descarte"}),
    ("Comprovante + aviso de cancelamento", "financeiro@lojasbeta.com.br", "Pagamento de setembro",
     "Segue o comprovante de setembro. Aproveito para avisar que, como o sistema ficou fora do ar a semana "
     "toda, vamos cancelar o contrato no fim do mês.",
     ["comprovante_set.pdf"], {"cancelamento"}),
    ("Reclamação sarcástica", "joao.lima@gmail.com", "Parabéns pelo serviço",
     "Adorei ser cobrado duas vezes este mês e ninguém responder o chat. Excelente atendimento, de verdade.",
     [], {"solicitacao_suporte"}),
    ("Cancelamento em inglês", "john.miller@acme.com", "Cancellation request",
     "Hi team, please cancel our subscription effective next month. Thanks, John.",
     [], {"cancelamento"}),
    ("'Cancelar' que não é cancelamento", "rh@empresa.com.br", "Reunião cancelada",
     "Pessoal, a reunião de alinhamento de quinta foi cancelada; remarcamos para segunda às 10h.",
     [], {"outro"}),
]

OLD_THREAD = [
    "Bom dia, o relatório de estoque não está atualizando desde segunda. Alguém pode olhar?",
    "Olá! Abrimos o chamado 4471 e o time técnico já está verificando, retornamos em breve.",
    "Alguma novidade? O pessoal da loja está fazendo a contagem à mão.",
    "Identificamos a falha na integração com o ERP e aplicamos uma correção paliativa.",
    "O relatório voltou, mas os valores de ontem vieram duplicados.",
    "Corrigimos a duplicidade. Podem confirmar se está tudo certo?",
]


class EmailTriageExample(Example):
    number = 4
    slug = "triagem-emails"
    title = "Classificação e triagem de e-mails"
    summary = ("Classifica cada e-mail (fatura/comprovante, suporte, proposta comercial, spam ou cancelamento) "
               "e dispara a ação seguinte: leitura de anexos, ticket, comercial, descarte ou retenção.")

    def scenarios(self) -> list[Scenario]:
        cases = [self._triage(label, _email(sender, subject, body, attachments), f"{subject} — {body}", accepted)
                 for label, sender, subject, body, attachments, accepted in REGULAR]
        return [Scenario(
            title="Caixa de entrada corporativa",
            description="Um e-mail típico de cada categoria.",
            cases=cases,
            metrics=_distribution(cases),
        )]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [self._triage(label, _email(sender, subject, body, attachments), f"{subject} — {body}", accepted)
                  for label, sender, subject, body, attachments, accepted in TRICKY]
        quoted = _quoted_thread(rounds=5)
        long_threads = [
            self._triage(
                "Pedido no topo, histórico abaixo",
                _email("gerente@redemercados.com.br", "ENC: Chamado 4471 - relatório de estoque",
                       "Pessoal, conforme conversamos, por favor cancelem o contrato da filial Campinas a partir de "
                       "novembro. Segue o histórico abaixo.\n\n" + quoted, []),
                f"Pedido de cancelamento na primeira linha + {len(OLD_THREAD) * 5} mensagens antigas citadas",
                {"cancelamento"},
            ),
            self._triage(
                "Histórico acima, pedido no fim",
                _email("gerente@redemercados.com.br", "RE: Chamado 4471 - relatório de estoque",
                       quoted + "\n\nEnfim, depois de tudo isso decidimos cancelar o contrato da filial Campinas "
                                "a partir de novembro.", []),
                f"{len(OLD_THREAD) * 5} mensagens antigas citadas + pedido de cancelamento na última linha",
                {"cancelamento"},
            ),
        ]
        return [
            Scenario(
                title="E-mails ambíguos e disfarçados",
                description="Phishing com cara de fatura, e-mail com duas intenções, sarcasmo, outro idioma e "
                            "a palavra 'cancelar' fora de contexto.",
                bonus=True,
                stress="Categorias que se sobrepõem e palavras-chave enganosas.",
                cases=tricky,
                metrics=_distribution(tricky),
            ),
            Scenario(
                title="Thread longa encaminhada",
                description="Mesmo pedido de cancelamento, uma vez antes e outra depois de um histórico citado extenso.",
                bonus=True,
                stress="State grande: mostra se a posição da informação decisiva muda a classificação.",
                cases=long_threads,
                metrics=_distribution(long_threads),
            ),
        ]

    def _triage(self, label: str, state: dict, summary: str, accepted: set[str]) -> Case:
        expected = " ou ".join(sorted(accepted))
        call = self._ask(state, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)

        options = ranked(call.choice("categoria"))
        (top, top_p), (second, second_p) = options[0], options[1]
        category = top if top_p >= MIN_TOP_PROBABILITY else MANUAL
        action = ACTIONS[category]
        if category != MANUAL and second_p >= COPY_PROBABILITY:
            action += f" + cópia: {ACTIONS[second]}"
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=category,
            expected=expected,
            passed=category in accepted,
            details={
                "ação disparada": action,
                "1ª opção": f"{top} ({top_p:.2f})",
                "2ª opção": f"{second} ({second_p:.2f})",
                "regras": f"1ª < {MIN_TOP_PROBABILITY} → triagem manual; 2ª ≥ {COPY_PROBABILITY} → cópia",
            },
        )


def _email(sender: str, subject: str, body: str, attachments: list[str]) -> dict:
    return {"remetente": sender, "assunto": subject, "corpo": body, "anexos": attachments}


def _quoted_thread(rounds: int) -> str:
    lines = []
    for index in range(rounds):
        for position, message in enumerate(OLD_THREAD):
            author = "suporte@fornecedor.com.br" if position % 2 else "gerente@redemercados.com.br"
            lines.append(f"> Em {index + 1:02d}/09, {author} escreveu: {message}")
    return "\n".join(lines)


def _distribution(cases: list[Case]) -> dict:
    outcomes = [case.outcome for case in cases]
    return {category: outcomes.count(category) for category in ACTIONS if outcomes.count(category)}
