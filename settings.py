import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class ModelProvider(str, Enum):
    JEV = "jev"
    LAYA = "laya"


@dataclass(frozen=True)
class Settings:
    model_provider: ModelProvider
    jev_api_url: str
    jev_api_key: str | None
    jev_model: str
    laya_api_url: str
    laya_model: str
    request_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model_provider=ModelProvider(os.getenv("MODEL_PROVIDER", "laya").lower()),
            jev_api_url=os.getenv("JEV_API_URL", "https://api.typesafe.ai/v1/systemone"),
            jev_api_key=os.getenv("JEV_API_KEY"),
            jev_model=os.getenv("JEV_MODEL", "jev-latest"),
            laya_api_url=os.getenv("LAYA_API_URL", "http://0.0.0.0:8000/v1/systemone"),
            laya_model=os.getenv("LAYA_MODEL", "laya-latest"),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "60")),
        )


settings = Settings.from_env()
