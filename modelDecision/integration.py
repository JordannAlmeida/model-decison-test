from abc import ABC, abstractmethod
from typing import Any

from modelDecision.scheme import Request, Response


class ModelDecision(ABC):

    @abstractmethod
    def call(self, request: Request, sent: list[dict[str, Any]] | None = None) -> Response:
        """Answers `request`. `sent` receives, in order, each body actually POSTed to the provider,
        which may differ from `request` (e.g. Laya adds its own controls and splits choices)."""
