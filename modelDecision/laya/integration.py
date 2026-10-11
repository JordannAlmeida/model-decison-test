from typing import Any

import httpx

from modelDecision.integration import ModelDecision
from modelDecision.scheme import Request, Response

# Checkpoint names a request may pin; any other model (e.g. "laya-latest") gets the default checkpoint.
_CHECKPOINTS = {"english", "multilingual", "typed-decisions"}


class LayaModelDecision(ModelDecision):
    """Calls a Laya server running locally (docker).

    The Jev-shaped request is sent with the Laya controls the HTTP API accepts (docs/http-api.md):

    - `model` pins the multilingual checkpoint. Left to the router, short Portuguese text without
      accents is detected as English and answered by the English checkpoint.
    - `max_len` / `head_max_len` widen the token windows. The multilingual checkpoint reads up to
      8,192 tokens but ships with 1,024, cutting the end of long states, and its options share
      256 tokens, which leaves ~6-8 tokens per label on a 30-40 option choice.
    - A choice with more than `tournament_group` options is narrowed first, as
      `laya.predict_tournament` does in-process: its labels are answered in groups and the question
      is asked again over the group winners. Its probabilities are over those finalists only
      (eliminated labels come back as 0).
    """

    def __init__(
        self,
        api_url: str,
        timeout: float = 60.0,
        checkpoint: str = "multilingual",
        max_len: int = 8192,
        head_max_len: int = 1024,
        tournament_group: int = 16,
    ):
        self._api_url = api_url
        self._timeout = timeout
        self._checkpoint = checkpoint
        self._max_len = max_len
        self._head_max_len = head_max_len
        self._tournament_group = tournament_group

    def call(self, request: Request, sent: list[dict[str, Any]] | None = None) -> Response:
        payload = request.model_dump(mode="json", exclude_none=True)
        if payload["model"] not in _CHECKPOINTS:
            payload["model"] = self._checkpoint
        payload["max_len"] = self._max_len
        payload["head_max_len"] = self._head_max_len

        questions = payload["questions"]
        finalists = self._tournament(payload, sent)
        payload["questions"] = {
            qid: _narrowed(question, finalists[qid]) if qid in finalists else question
            for qid, question in questions.items()
        }
        body = self._post(payload, sent)
        for qid in finalists:
            probabilities = body["answers"][qid]["probabilities"]
            body["answers"][qid]["probabilities"] = {
                label: probabilities.get(label, 0.0) for label in questions[qid]["criteria"]
            }
        return Response.model_validate(body)

    def _tournament(self, payload: dict[str, Any], sent: list[dict[str, Any]] | None) -> dict[str, list[str]]:
        """Finalist labels of every choice larger than the group size."""
        group = self._tournament_group
        labels = {
            qid: list(question["criteria"])
            for qid, question in payload["questions"].items()
            if question["type"] == "choice" and len(question["criteria"]) > group
        }
        while True:
            groups = []
            for qid, remaining in labels.items():
                parts = -(-len(remaining) // group)
                if parts > 1:
                    size = len(remaining)
                    groups += [(qid, remaining[i * size // parts:(i + 1) * size // parts]) for i in range(parts)]
            if not groups:
                return labels
            round_questions = {
                str(i): _narrowed(payload["questions"][qid], kept) for i, (qid, kept) in enumerate(groups)
            }
            answers = self._post({**payload, "questions": round_questions}, sent)["answers"]
            winners: dict[str, list[str]] = {}
            for i, (qid, _kept) in enumerate(groups):
                winners.setdefault(qid, []).append(answers[str(i)]["choice"])
            labels.update(winners)

    def _post(self, payload: dict[str, Any], sent: list[dict[str, Any]] | None) -> dict[str, Any]:
        if sent is not None:
            sent.append(payload)
        http_response = httpx.post(self._api_url, json=payload, timeout=self._timeout)
        http_response.raise_for_status()
        return http_response.json()


def _narrowed(question: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """The same choice restricted to `labels`, in criteria order."""
    kept = set(labels)
    return {**question, "criteria": {label: text for label, text in question["criteria"].items() if label in kept}}
