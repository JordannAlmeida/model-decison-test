from modelDecision.integration import ModelDecision
from modelDecision.jev.integration import JevModelDecision
from modelDecision.laya.integration import LayaModelDecision
from settings import ModelProvider, Settings, settings as default_settings


def create_model_decision(
    provider: ModelProvider | None = None,
    settings: Settings = default_settings,
) -> ModelDecision:
    provider = provider or settings.model_provider

    match provider:
        case ModelProvider.JEV:
            if not settings.jev_api_key:
                raise ValueError("JEV_API_KEY must be set to use the Jev provider")
            return JevModelDecision(
                api_url=settings.jev_api_url,
                api_key=settings.jev_api_key,
                timeout=settings.request_timeout,
            )
        case ModelProvider.LAYA:
            return LayaModelDecision(
                api_url=settings.laya_api_url,
                timeout=settings.request_timeout,
            )
        case _:
            raise ValueError(f"Unsupported model provider: {provider}")
