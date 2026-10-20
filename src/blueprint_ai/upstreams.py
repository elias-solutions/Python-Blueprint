from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import SecretStr

from blueprint_ai.settings import Settings


@dataclass(frozen=True)
class Upstream:
    id: str
    base_url: str
    models: frozenset[str]
    api_key: SecretStr | None = None

    def allows(self, model: str) -> bool:
        return model in self.models

    def headers(self) -> dict[str, str]:
        if self.api_key is None:
            return {}
        return {"Authorization": f"Bearer {self.api_key.get_secret_value()}"}


class UpstreamRegistry:
    def __init__(self, upstreams: Iterable[Upstream]) -> None:
        self._upstreams = {upstream.id: upstream for upstream in upstreams}

    def find(self, upstream_id: str) -> Upstream | None:
        return self._upstreams.get(upstream_id)


def build_registry(settings: Settings) -> UpstreamRegistry:
    return UpstreamRegistry(
        [
            Upstream(
                id="ollama",
                base_url=settings.ollama_base_url,
                models=frozenset(settings.ollama_models),
            ),
            Upstream(
                id="openai",
                base_url=settings.openai_base_url,
                models=frozenset(settings.openai_models),
                api_key=settings.openai_api_key,
            ),
        ]
    )
