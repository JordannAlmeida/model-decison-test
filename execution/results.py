"""Neutral result/trace model shared by the examples (producers) and the report (consumer).

Neither side imports the other: examples fill these objects, `main.py` serializes them to
JSON and the report renders them, from memory or from the saved JSON.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from modelDecision.scheme import ChoiceAnswer, NoulAnswer, Response, ScoreAnswer


class Call(BaseModel):
    """One request sent to the decision model, with its response (or error)."""

    label: str | None = None
    request: dict[str, Any]
    response: Response | None = None
    error: str | None = None
    latency_ms: float

    @property
    def failed(self) -> bool:
        return self.response is None

    def choice(self, key: str) -> ChoiceAnswer:
        return self._answer(key, ChoiceAnswer)

    def score(self, key: str) -> ScoreAnswer:
        return self._answer(key, ScoreAnswer)

    def noul(self, key: str) -> float:
        return self._answer(key, NoulAnswer).noul

    def _answer[T](self, key: str, kind: type[T]) -> T:
        if self.response is None:
            raise RuntimeError(f"call failed, no answer for '{key}': {self.error}")
        answer = self.response.answers[key]
        if not isinstance(answer, kind):
            raise TypeError(f"answer '{key}' is {type(answer).__name__}, expected {kind.__name__}")
        return answer


class Case(BaseModel):
    """One input evaluated by an example: the calls made and the decision taken."""

    label: str
    input_summary: str | None = None
    calls: list[Call]
    outcome: str
    expected: str | None = None
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @classmethod
    def from_failure(
        cls,
        label: str,
        calls: list[Call],
        expected: str | None = None,
        input_summary: str | None = None,
    ) -> "Case":
        error = next((call.error for call in calls if call.error), "falha desconhecida")
        return cls(
            label=label,
            input_summary=input_summary,
            calls=calls,
            outcome="erro na chamada ao modelo",
            expected=expected,
            passed=False if expected is not None else None,
            error=error,
        )


class Scenario(BaseModel):
    title: str
    description: str
    bonus: bool = False
    # which limit of the decision model a bonus scenario tries to reach
    stress: str | None = None
    cases: list[Case]
    # aggregated figures computed by the example (e.g. estimated savings, precision@3)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ExampleResult(BaseModel):
    number: int
    slug: str
    title: str
    summary: str
    scenarios: list[Scenario] = Field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0


class RunResult(BaseModel):
    provider: str
    model: str
    api_url: str
    started_at: datetime
    finished_at: datetime
    examples: list[ExampleResult]

    def save_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load_json(cls, path: Path) -> "RunResult":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
