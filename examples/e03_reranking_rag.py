"""3. Re-ordenação de trechos recuperados em RAG (reranking).

A busca vetorial é simulada: cada pergunta já vem com 8 trechos e a similaridade que a busca
teria dado. O modelo de decisão avalia cada par (pergunta, trecho) com um Noul, como no
cookbook de re-ranking, e só os 3 trechos mais bem avaliados seguem para o prompt final.
"""

from dataclasses import dataclass

from examples.base import Example
from execution.results import Case, Scenario
from modelDecision.scheme import NoulCriteria, NoulQuestion, Type

TOP_K = 3

QUESTIONS = {
    "responde": NoulQuestion(
        type=Type.NOUL,
        instructions="O `trecho` contém a informação que responde à `pergunta`?",
        criteria=NoulCriteria(
            true="O trecho traz a resposta ou um passo concreto que resolve a pergunta",
            false="O trecho só trata de tema parecido, repete as palavras da pergunta ou responde outra coisa",
        ),
    ),
}


@dataclass(frozen=True)
class Chunk:
    id: str
    similarity: float  # what the (mocked) vector search returned
    text: str


@dataclass(frozen=True)
class Query:
    label: str
    question: str
    chunks: list[Chunk]
    essential: set[str]  # must reach the top-k
    relevant: set[str]   # used for precision@k


BOLETO_CHUNKS = [
    Chunk("c1", 0.91, "A segunda via do boleto é um dos assuntos mais buscados na nossa central de ajuda. "
                      "Neste artigo reunimos as dúvidas frequentes sobre boletos e parcelas."),
    Chunk("c2", 0.89, "Para emitir a segunda via do boleto, acesse o Portal do Cliente, entre em Financeiro > "
                      "Boletos, selecione a parcela e clique em 'Gerar segunda via'. O novo boleto já vem com "
                      "juros atualizados."),
    Chunk("c3", 0.87, "Boletos vencidos há mais de 60 dias não podem ser reemitidos pelo portal; nesse caso, "
                      "fale com a central de relacionamento pelo telefone 0800 000 0000."),
    Chunk("c4", 0.86, "O boleto da taxa de condomínio é emitido pela administradora do condomínio, e não pela "
                      "construtora."),
    Chunk("c5", 0.84, "Você também pode pedir a segunda via pelo WhatsApp oficial: envie a palavra 'boleto' e "
                      "informe o CPF do titular do contrato."),
    Chunk("c6", 0.82, "Para antecipar parcelas com desconto, solicite uma simulação de amortização no Portal do "
                      "Cliente."),
    Chunk("c7", 0.80, "Em caso de atraso, são cobrados multa de 2% e juros de 1% ao mês sobre o valor da "
                      "parcela, conforme o contrato."),
    Chunk("c8", 0.78, "O IPTU do imóvel passa a ser responsabilidade do cliente a partir da entrega das chaves."),
]

VISTORIA_CHUNKS = [
    Chunk("d1", 0.90, "O prazo de garantia para problemas estruturais é de 5 anos a partir da entrega das chaves."),
    Chunk("d2", 0.88, "As chaves só são entregues após a assinatura do contrato de financiamento e o pagamento "
                      "do ITBI."),
    Chunk("d3", 0.86, "Durante a vistoria, confira portas, janelas, pisos e instalações elétricas e anote tudo "
                      "no termo de vistoria."),
    Chunk("d4", 0.85, "A vistoria de entrega deve ser agendada em até 15 dias após o recebimento do comunicado "
                      "de entrega, pelo Portal do Cliente."),
    Chunk("d5", 0.83, "Mudanças só podem ocorrer de segunda a sábado, das 8h às 18h, com agendamento na portaria."),
    Chunk("d6", 0.81, "Se o cliente não agendar a vistoria dentro do prazo, a entrega das chaves passa para a "
                      "próxima janela disponível."),
    Chunk("d7", 0.79, "A assistência técnica pós-entrega pode ser solicitada pelo Portal do Cliente, em 'Chamados'."),
    Chunk("d8", 0.77, "O comunicado de entrega é enviado por e-mail e SMS cerca de 30 dias antes da data prevista."),
]

DISTRATO_CHUNKS = [
    Chunk("f1", 0.93, "Cancelar a compra do apartamento e receber o dinheiro de volta são dúvidas comuns. "
                      "Veja abaixo os principais tópicos sobre o assunto."),
    Chunk("f2", 0.90, "Não é possível cancelar o agendamento da vistoria pelo telefone; use o Portal do Cliente."),
    Chunk("f3", 0.88, "Até 2018, o distrato seguia apenas o contrato e não havia limite legal para a multa."),
    Chunk("f4", 0.87, "Compras de móveis planejados na loja parceira podem ser canceladas em até 7 dias com "
                      "reembolso integral."),
    Chunk("f5", 0.85, "Distrato: o comprador pode desistir da compra do imóvel; a construtora devolve os valores "
                      "pagos, retendo até 25% como multa, conforme a Lei 13.786/2018."),
    Chunk("f6", 0.83, "O FGTS usado na entrada volta para a conta vinculada do trabalhador em caso de distrato."),
    Chunk("f7", 0.81, "Para cancelar a assinatura da newsletter, clique em 'descadastrar' no rodapé do e-mail."),
    Chunk("f8", 0.79, "No distrato, a devolução dos valores é feita em parcela única em até 180 dias após a "
                      "assinatura do termo."),
]

MANUAL_SECTIONS = [
    "Bem-vindo ao seu novo lar! Este manual reúne as orientações de uso, conservação e manutenção do imóvel.",
    "As paredes internas foram executadas em bloco cerâmico; para fixar quadros e prateleiras, utilize buchas "
    "adequadas e evite furar a menos de 30 cm dos interruptores, por onde passam os eletrodutos.",
    "Os pisos cerâmicos devem ser limpos com pano úmido e detergente neutro; evite produtos abrasivos, palha de "
    "aço e ácidos, que removem o brilho e danificam o rejunte.",
    "As esquadrias de alumínio precisam de limpeza dos trilhos a cada três meses; mantenha os drenos livres para "
    "que a água da chuva não se acumule.",
    "A instalação de ar-condicionado deve respeitar o ponto previsto em projeto e a carga elétrica do circuito; "
    "consulte o síndico antes de alterar a fachada.",
    "O sistema de aquecimento a gás exige revisão anual feita por empresa credenciada; nunca obstrua a ventilação "
    "permanente da área de serviço.",
    "Reformas que alterem paredes, pisos ou instalações devem ser comunicadas ao condomínio com laudo de um "
    "responsável técnico, conforme a norma de reformas em edificações.",
    "Os prazos de garantia variam por sistema: revestimentos, 1 ano; instalações hidráulicas, 3 anos; estrutura, 5 anos.",
]


class RagRerankingExample(Example):
    number = 3
    slug = "reranking-rag"
    title = "Reranking de trechos recuperados em RAG"
    summary = ("Atribui uma nota de relevância a cada trecho devolvido pela busca vetorial (mock) e envia só os "
               f"{TOP_K} melhores para o prompt final, reduzindo ruído e custo de contexto.")

    def scenarios(self) -> list[Scenario]:
        queries = [
            Query("Segunda via do boleto", "Como faço para emitir a segunda via do boleto da parcela do meu apartamento?",
                  BOLETO_CHUNKS, essential={"c2", "c5"}, relevant={"c2", "c3", "c5"}),
            Query("Prazo da vistoria", "Qual é o prazo para agendar a vistoria do apartamento antes da entrega das chaves?",
                  VISTORIA_CHUNKS, essential={"d4"}, relevant={"d4", "d6", "d8"}),
        ]
        return [self._scenario("Base de conhecimento de uma construtora",
                               "Perguntas de clientes com trechos de FAQ recuperados por similaridade.",
                               queries)]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [
            Query("Distrato com distratores lexicais", "Posso cancelar a compra do apartamento e receber o dinheiro de volta?",
                  DISTRATO_CHUNKS, essential={"f5"}, relevant={"f5", "f6", "f8"}),
            Query("Pergunta composta (multi-hop)",
                  "Quanto vou pagar a mais se emitir a segunda via de um boleto vencido há 10 dias?",
                  BOLETO_CHUNKS, essential={"c7"}, relevant={"c2", "c7"}),
        ]
        long_chunk = Chunk("c2", 0.89, " ".join(MANUAL_SECTIONS * 5) + " " + BOLETO_CHUNKS[1].text)
        buried = [
            Query("Resposta no fim de um trecho longo",
                  "Como faço para emitir a segunda via do boleto da parcela do meu apartamento?",
                  [long_chunk if chunk.id == "c2" else chunk for chunk in BOLETO_CHUNKS],
                  essential={"c2", "c5"}, relevant={"c2", "c3", "c5"}),
        ]
        return [
            self._scenario("Distratores e perguntas compostas",
                           "Trechos que repetem as palavras da pergunta sem respondê-la, regras desatualizadas e "
                           "uma pergunta que depende de juntar dois trechos.",
                           tricky, stress="Separar sobreposição de palavras de resposta real."),
            self._scenario("Trecho longo com a resposta enterrada",
                           f"O trecho c2 vira um manual do proprietário inteiro (~{len(long_chunk.text.split())} "
                           "palavras) com as instruções de segunda via só no último parágrafo.",
                           buried, stress="State grande: o trecho excede o contexto e a resposta fica no fim."),
        ]

    def _scenario(self, title: str, description: str, queries: list[Query], stress: str | None = None) -> Scenario:
        cases = [self._rerank(query) for query in queries]
        ok = [case for case in cases if case.error is None]
        metrics = {}
        if ok:
            metrics = {
                f"precisão@{TOP_K} média (busca vetorial)": _mean(case.details["precisao_vetorial"] for case in ok),
                f"precisão@{TOP_K} média (após rerank)": _mean(case.details["precisao_rerank"] for case in ok),
                "trechos enviados ao LLM por pergunta": f"{TOP_K} de {len(queries[0].chunks)}",
            }
        return Scenario(title=title, description=description, bonus=stress is not None, stress=stress,
                        cases=cases, metrics=metrics)

    def _rerank(self, query: Query) -> Case:
        expected = f"{', '.join(sorted(query.essential))} no top-{TOP_K}"
        states = [{"pergunta": query.question, "trecho": chunk.text} for chunk in query.chunks]
        calls = self._ask_each(states, QUESTIONS, [f"trecho {chunk.id}" for chunk in query.chunks])
        if any(call.failed for call in calls):
            return Case.from_failure(query.label, calls, expected, query.question)

        scored = sorted(zip(query.chunks, (call.noul("responde") for call in calls), strict=True),
                        key=lambda pair: pair[1], reverse=True)
        top = [chunk.id for chunk, _ in scored[:TOP_K]]
        vector_top = [chunk.id for chunk in sorted(query.chunks, key=lambda c: c.similarity, reverse=True)[:TOP_K]]
        vector_rank = {chunk.id: position for position, chunk in
                       enumerate(sorted(query.chunks, key=lambda c: c.similarity, reverse=True), start=1)}
        return Case(
            label=query.label,
            input_summary=query.question,
            calls=calls,
            outcome=f"top-{TOP_K}: {', '.join(top)}",
            expected=expected,
            passed=query.essential <= set(top),
            details={
                "precisao_vetorial": round(len(set(vector_top) & query.relevant) / TOP_K, 3),
                "precisao_rerank": round(len(set(top) & query.relevant) / TOP_K, 3),
                f"top-{TOP_K} da busca vetorial": ", ".join(vector_top),
                "ranking": [
                    {
                        "posição": position,
                        "trecho": chunk.id,
                        "relevância (noul)": round(score, 3),
                        "posição na busca vetorial": vector_rank[chunk.id],
                        "similaridade vetorial": chunk.similarity,
                        "relevante?": "sim" if chunk.id in query.relevant else "não",
                        "texto": chunk.text if len(chunk.text) < 160 else chunk.text[:80] + " (…) " + chunk.text[-70:],
                    }
                    for position, (chunk, score) in enumerate(scored, start=1)
                ],
            },
        )


def _mean(values) -> float:
    values = list(values)
    return round(sum(values) / len(values), 3)
