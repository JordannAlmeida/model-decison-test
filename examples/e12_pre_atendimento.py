"""12. Triagem inicial de pré-atendimento especializado.

No primeiro contato, o modelo de decisão identifica a área do problema (Choice) para disparar o
formulário de coleta certo: área do direito num escritório de advocacia, especialidade numa
clínica. Na clínica, um Noul com limiar baixo verifica sinais de emergência antes de tudo, porque
deixar passar uma emergência custa muito mais do que um falso alarme.
"""

from examples.base import Example, ranked
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, NoulQuestion, Type

HUMAN = "atendente humano"
EMERGENCY = "emergência: orientar a ligar 192 (SAMU)"
MIN_TOP_PROBABILITY = 0.45
SECONDARY_PROBABILITY = 0.25
# low on purpose: a missed emergency is far more costly than a false alarm
EMERGENCY_THRESHOLD = 0.3

LAW_AREAS = {
    "trabalhista": "Relação de emprego: demissão, carteira assinada, horas extras, verbas rescisórias",
    "familia": "Divórcio, guarda de filhos, pensão alimentícia, inventário e união estável",
    "consumidor": "Produto com defeito, serviço mal prestado, cobrança indevida por empresa",
    "criminal": "Crimes, boletim de ocorrência, inquérito e defesa em processo penal",
    "previdenciario": "INSS: aposentadoria, auxílio-doença, BPC e pensão por morte",
    "imobiliario": "Compra e venda de imóvel, aluguel, despejo e usucapião",
    "tributario": "Impostos, Receita Federal, multas fiscais e malha fina",
    "outro": "Assuntos fora das áreas acima",
}
LAW_FORMS = {
    "trabalhista": ["período trabalhado", "carteira assinada?", "motivo da saída", "salário"],
    "familia": ["estado civil", "filhos menores?", "bens a partilhar"],
    "consumidor": ["empresa", "data da compra", "nota fiscal", "protocolos de atendimento"],
    "criminal": ["data do fato", "boletim de ocorrência", "intimações recebidas"],
    "previdenciario": ["idade", "tempo de contribuição", "número do benefício negado"],
    "imobiliario": ["endereço do imóvel", "tipo de contrato", "valores envolvidos"],
    "tributario": ["tipo de imposto", "ano-calendário", "notificação recebida"],
}

SPECIALTIES = {
    "cardiologia": "Coração e pressão arterial",
    "dermatologia": "Pele, cabelo, unhas e pintas",
    "ortopedia": "Ossos, articulações, entorses e fraturas",
    "pediatria": "Crianças e adolescentes",
    "ginecologia": "Saúde da mulher, gestação e menstruação",
    "psiquiatria": "Ansiedade, depressão, insônia e saúde mental",
    "oftalmologia": "Olhos e visão",
    "clinica_geral": "Sintomas gerais, check-up e casos sem especialidade clara",
}

EXTENDED_SPECIALTIES = {
    **SPECIALTIES,
    "otorrinolaringologia": "Ouvido, nariz e garganta, zumbido, sinusite",
    "endocrinologia": "Hormônios, tireoide, diabetes e obesidade",
    "urologia": "Rins, bexiga, próstata e cálculo renal",
    "nefrologia": "Doenças dos rins e insuficiência renal",
    "gastroenterologia": "Estômago, intestino, fígado e refluxo",
    "neurologia": "Enxaqueca, convulsões, formigamento e AVC",
    "pneumologia": "Pulmões, asma, bronquite e falta de ar crônica",
    "reumatologia": "Artrite, lúpus e dores articulares inflamatórias",
    "hematologia": "Sangue, anemia e coagulação",
    "oncologia": "Câncer e tumores",
    "infectologia": "Infecções, HIV, hepatites e doenças tropicais",
    "alergologia": "Alergias respiratórias, alimentares e de pele",
    "angiologia": "Varizes, circulação e trombose",
    "geriatria": "Saúde do idoso",
    "mastologia": "Mamas e nódulos mamários",
    "proctologia": "Reto e ânus, hemorroidas",
    "nutrologia": "Nutrição e deficiências nutricionais",
    "fisiatria": "Reabilitação física",
    "medicina_do_esporte": "Lesões e desempenho no esporte",
    "cirurgia_plastica": "Cirurgias estéticas e reparadoras",
    "cirurgia_geral": "Hérnias, vesícula e apendicite",
    "obstetricia": "Pré-natal e parto",
    "andrologia": "Saúde reprodutiva masculina",
    "homeopatia": "Tratamentos homeopáticos",
    "acupuntura": "Tratamento com agulhas",
    "medicina_do_sono": "Apneia e distúrbios do sono",
    "psicologia": "Psicoterapia, sem prescrição de remédios",
    "fonoaudiologia": "Fala, voz e deglutição",
    "odontologia": "Dentes e gengiva",
    "nutricao": "Plano alimentar e reeducação alimentar",
    "medicina_do_trabalho": "Exames admissionais e saúde ocupacional",
    "genetica_medica": "Doenças hereditárias e aconselhamento genético",
}


def _area_question(options: dict[str, str], instructions: str) -> ChoiceQuestion:
    return ChoiceQuestion(type=Type.CHOICE, instructions=instructions, criteria=options)


LAW_QUESTIONS = {"area": _area_question(LAW_AREAS, "Qual área do direito trata o problema descrito na `mensagem`?")}
CLINIC_QUESTIONS = {
    "area": _area_question(SPECIALTIES, "Qual especialidade médica deve atender o paciente da `mensagem`?"),
    "sinais_de_emergencia": NoulQuestion(
        type=Type.NOUL,
        instructions="A `mensagem` descreve sinais de emergência médica, como dor no peito, falta de ar, desmaio, "
                     "sangramento intenso ou confusão súbita?",
    ),
}
EXTENDED_QUESTIONS = {
    "area": _area_question(EXTENDED_SPECIALTIES, "Qual especialidade de saúde deve atender o paciente da `mensagem`?"),
}

LAW_CASES = [
    ("Sem carteira e sem rescisão", "Trabalhei 3 anos sem carteira assinada e fui dispensado sem receber nada.",
     {"trabalhista"}),
    ("Divórcio e guarda", "Quero me divorciar e definir a guarda dos meus dois filhos.", {"familia"}),
    ("Geladeira com defeito", "Comprei uma geladeira que parou em 10 dias e a loja se recusa a trocar.",
     {"consumidor"}),
    ("Aposentadoria negada", "Meu pai tem 66 anos e o INSS negou a aposentadoria dele.", {"previdenciario"}),
]
CLINIC_CASES = [
    ("Criança com febre e manchas", "Minha filha de 4 anos está com febre e manchas vermelhas pelo corpo há dois "
                                    "dias.", {"pediatria"}),
    ("Pinta que mudou", "Tenho uma pinta nas costas que mudou de cor e está coçando.", {"dermatologia"}),
    ("Joelho torcido", "Torci o joelho jogando futebol e está inchado.", {"ortopedia"}),
    ("Ansiedade e insônia", "Ando muito ansioso, sem dormir direito há semanas, e isso está atrapalhando o "
                            "trabalho.", {"psiquiatria"}),
]
TRICKY = [
    ("Duas áreas: demissão e divórcio", LAW_QUESTIONS, "Fui demitida grávida e meu marido quer o divórcio.",
     {"trabalhista", "familia"}),
    ("Linguagem coloquial, sem acentos", LAW_QUESTIONS,
     "meu patrao nao assinou minha carteira e me mandou embora sem pagar nada oq eu faço", {"trabalhista"}),
    ("Multa da Receita", LAW_QUESTIONS, "Caí na malha fina e recebi uma multa da Receita no imposto de renda.",
     {"tributario"}),
    ("Emergência disfarçada de agendamento", CLINIC_QUESTIONS,
     "Oi, queria marcar com cardiologista para semana que vem. Desde cedo sinto um aperto no peito que vai para o "
     "braço esquerdo e estou suando frio, mas deve ser nada.", {EMERGENCY}),
    ("Palavras alarmantes sem emergência", CLINIC_QUESTIONS,
     "Quero fazer um check-up do coração porque meu pai teve infarto no ano passado.", {"cardiologia"}),
]
EXTENDED_CASES = [
    ("Zumbido no ouvido", "Tenho um zumbido no ouvido direito há meses, piora à noite.", {"otorrinolaringologia"}),
    ("Tireoide", "Meu exame de TSH veio alterado e estou ganhando peso sem motivo.", {"endocrinologia"}),
    ("Pedra no rim", "Já tive pedra no rim duas vezes e quero prevenir uma nova crise.", {"urologia", "nefrologia"}),
    ("Ronco e apneia", "Minha esposa diz que eu paro de respirar enquanto durmo e ronco muito alto.",
     {"medicina_do_sono", "pneumologia", "otorrinolaringologia"}),
    ("Dor de dente", "Estou com uma dor de dente latejante desde ontem.", {"odontologia"}),
]


class SpecializedIntakeExample(Example):
    number = 12
    slug = "pre-atendimento"
    title = "Triagem inicial de pré-atendimento especializado"
    summary = ("Identifica no primeiro contato a área do problema (direito ou especialidade médica) para disparar "
               "o formulário de coleta certo; na clínica, detecta sinais de emergência antes de qualquer coisa.")

    def scenarios(self) -> list[Scenario]:
        law = [self._triage(label, LAW_QUESTIONS, text, accepted) for label, text, accepted in LAW_CASES]
        clinic = [self._triage(label, CLINIC_QUESTIONS, text, accepted) for label, text, accepted in CLINIC_CASES]
        return [
            Scenario(title="Escritório de advocacia", description="Mensagens de primeiro contato via WhatsApp.",
                     cases=law, metrics=_routes(law)),
            Scenario(title="Clínica médica", description="Pedidos de agendamento com a queixa principal.",
                     cases=clinic, metrics=_routes(clinic)),
        ]

    def bonus_scenarios(self) -> list[Scenario]:
        tricky = [self._triage(label, questions, text, accepted) for label, questions, text, accepted in TRICKY]
        extended = [self._triage(label, EXTENDED_QUESTIONS, text, accepted)
                    for label, text, accepted in EXTENDED_CASES]
        return [
            Scenario(
                title="Fronteiras e riscos",
                description="Problema que envolve duas áreas, escrita coloquial, emergência escondida num pedido de "
                            "agendamento e palavras alarmantes sem emergência.",
                bonus=True,
                stress="Casos na fronteira entre áreas e o custo assimétrico de não detectar uma emergência.",
                cases=tricky,
                metrics=_routes(tricky),
            ),
            Scenario(
                title=f"Lista ampla com {len(EXTENDED_SPECIALTIES)} especialidades",
                description="O mesmo Choice da clínica, agora com todas as especialidades de um plano de saúde, "
                            "incluindo vizinhas próximas (urologia × nefrologia, psiquiatria × psicologia).",
                bonus=True,
                stress="Muitas opções parecidas num único Choice.",
                cases=extended,
                metrics=_routes(extended),
            ),
        ]

    def _triage(self, label: str, questions: dict, text: str, accepted: set[str]) -> Case:
        expected = " ou ".join(sorted(accepted))
        call = self._ask({"canal": "WhatsApp", "mensagem": text}, questions, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, text)

        options = ranked(call.choice("area"))
        (top, top_p), (second, second_p) = options[0], options[1]
        emergency = call.noul("sinais_de_emergencia") if "sinais_de_emergencia" in questions else None
        if emergency is not None and emergency >= EMERGENCY_THRESHOLD:
            route = EMERGENCY
        elif top_p >= MIN_TOP_PROBABILITY:
            route = top
        else:
            route = HUMAN
        details = {
            "1ª opção": f"{top} ({top_p:.2f})",
            "2ª opção": f"{second} ({second_p:.2f})",
            "verificar também": second if route == top and second_p >= SECONDARY_PROBABILITY else "—",
        }
        if emergency is not None:
            details["sinais de emergência"] = round(emergency, 3)
        if route in LAW_FORMS:
            details["formulário disparado"] = ", ".join(LAW_FORMS[route])
        return Case(
            label=label,
            input_summary=text,
            calls=[call],
            outcome=route,
            expected=expected,
            passed=route in accepted,
            details=details,
        )


def _routes(cases: list[Case]) -> dict:
    outcomes = [case.outcome for case in cases if case.error is None]
    return {
        "encaminhados direto": sum(1 for outcome in outcomes if outcome not in (HUMAN, EMERGENCY)),
        "atendente humano": outcomes.count(HUMAN),
        "emergências sinalizadas": outcomes.count(EMERGENCY),
    }
