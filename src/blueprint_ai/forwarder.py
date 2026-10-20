from dataclasses import dataclass
from typing import Any

import httpx

from blueprint_ai.upstreams import Upstream


@dataclass(frozen=True)
class UpstreamResponse:
    status_code: int
    body: bytes
    content_type: str


class UpstreamUnavailableError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class ChatForwarder:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def complete(self, upstream: Upstream, payload: dict[str, Any]) -> UpstreamResponse:
        try:
            response = await self._client.post(
                f"{upstream.base_url}/chat/completions",
                json=payload,
                headers=upstream.headers(),
            )
        except httpx.TimeoutException as error:
            raise UpstreamUnavailableError(504, f"Provider '{upstream.id}' timed out.") from error
        except httpx.TransportError as error:
            raise UpstreamUnavailableError(502, f"Provider '{upstream.id}' is not reachable.") from error
        return UpstreamResponse(
            status_code=response.status_code,
            body=response.content,
            content_type=response.headers.get("content-type", "application/json"),
        )
