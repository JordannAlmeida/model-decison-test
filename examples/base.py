import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import ClassVar

from execution.results import Call, Scenario
from modelDecision.integration import ModelDecision
from modelDecision.scheme import ChoiceAnswer, Content, Question, Request, ScoreAnswer


class Example(ABC):
    """A use case of the decision model.

    The decision model is injected (output of the factory), so an example knows nothing about
    which provider answers it, nor about how its results are reported.
    """

    number: ClassVar[int]
    slug: ClassVar[str]
    title: ClassVar[str]
    summary: ClassVar[str]

    def __init__(self, model_decision: ModelDecision, model: str, max_workers: int = 4) -> None:
        self._model_decision = model_decision
        self._model = model
        self._max_workers = max_workers

    @abstractmethod
    def scenarios(self) -> list[Scenario]:
        """Regular scenarios of the use case."""

    @abstractmethod
    def bonus_scenarios(self) -> list[Scenario]:
        """'Teste de fogo': scenarios built to push the decision model to its limits."""

    def _ask(self, state: Content, questions: dict[str, Question], label: str | None = None) -> Call:
        started = time.perf_counter()
        try:
            request = Request(state=state, model=self._model, questions=questions)
        except Exception as exc:
            return Call(label=label, request={"state": state, "questions": "<inválido>"},
                        error=_describe(exc), latency_ms=0.0)

        payload = request.model_dump(mode="json", exclude_none=True)
        sent: list[dict] = []
        try:
            response = self._model_decision.call(request, sent)
        except Exception as exc:
            return Call(label=label, request=payload, sent=sent, error=_describe(exc), latency_ms=_since(started))
        return Call(label=label, request=payload, sent=sent, response=response, latency_ms=_since(started))

    def _ask_each(
        self,
        states: Sequence[Content],
        questions: dict[str, Question],
        labels: Sequence[str],
    ) -> list[Call]:
        """Same questions over many independent states, in parallel, keeping the input order."""
        pairs = zip(states, labels, strict=True)
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(lambda pair: self._ask(pair[0], questions, pair[1]), pairs))


def ranked(answer: ChoiceAnswer) -> list[tuple[str, float]]:
    """Choice options sorted by probability, highest first."""
    return sorted(answer.probabilities.items(), key=lambda item: item[1], reverse=True)


def normalized(answer: ScoreAnswer) -> float:
    """Score mapped to 0..1, so scales with different lengths can be combined."""
    top_level = max(len(answer.legend) - 1, 1)
    return answer.score / top_level


def _since(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _describe(exc: Exception) -> str:
    body = getattr(getattr(exc, "response", None), "text", "")
    message = f"{type(exc).__name__}: {exc}"
    return f"{message} | {body[:500]}" if body else message
