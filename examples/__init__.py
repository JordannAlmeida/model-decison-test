from examples.base import Example
from examples.e01_roteamento_complexidade import ComplexityRoutingExample
from examples.e02_llm_as_judge import LlmAsJudgeExample
from examples.e03_reranking_rag import RagRerankingExample
from examples.e04_triagem_emails import EmailTriageExample
from examples.e05_risco_churn import ChurnRiskExample
from examples.e06_validacao_formularios import FormValidationExample
from examples.e07_triagem_suporte import SupportTriageExample
from examples.e08_guardrails import GuardrailsExample
from examples.e09_lead_scoring import LeadScoringExample
from examples.e10_sentimento_massa import SentimentBatchExample
from examples.e11_npc_jogo import NpcDecisionExample
from examples.e12_pre_atendimento import SpecializedIntakeExample

ALL_EXAMPLES: list[type[Example]] = [
    ComplexityRoutingExample,
    LlmAsJudgeExample,
    RagRerankingExample,
    EmailTriageExample,
    ChurnRiskExample,
    FormValidationExample,
    SupportTriageExample,
    GuardrailsExample,
    LeadScoringExample,
    SentimentBatchExample,
    NpcDecisionExample,
    SpecializedIntakeExample,
]
