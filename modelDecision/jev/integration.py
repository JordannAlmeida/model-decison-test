import httpx

from modelDecision.integration import ModelDecision
from modelDecision.scheme import Request, Response


class JevModelDecision(ModelDecision):
    """Calls the hosted Jev API (https://docs.typesafe.ai/api)."""

    def __init__(self, api_url: str, api_key: str, timeout: float = 60.0):
        self._api_url = api_url
        self._api_key = api_key
        self._timeout = timeout

    def call(self, request: Request) -> Response:
        http_response = httpx.post(
            self._api_url,
            json=request.model_dump(mode="json", exclude_none=True),
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self._timeout,
        )
        http_response.raise_for_status()
        return Response.model_validate(http_response.json())
