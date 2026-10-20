from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from blueprint_ai import chat_router
from blueprint_ai.auth import KeyResolver, TokenVerifier, jwks_key_resolver
from blueprint_ai.forwarder import ChatForwarder
from blueprint_ai.settings import Settings
from blueprint_ai.upstreams import build_registry


def create_app(settings: Settings | None = None, resolve_key: KeyResolver | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as client:
            app.state.forwarder = ChatForwarder(client)
            yield

    app = FastAPI(title="Python-Blueprint – AI Gateway", lifespan=lifespan)
    app.state.registry = build_registry(settings)
    app.state.verifier = TokenVerifier(
        settings.keycloak_issuer, resolve_key or jwks_key_resolver(settings.jwks_url)
    )
    app.include_router(chat_router.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "UP"}

    return app
