from abc import ABC, abstractmethod

from modelDecision.scheme import Request, Response


class ModelDecision(ABC):

    @abstractmethod
    def call(self, request: Request) -> Response:
        pass
