import time
from collections.abc import Callable, Iterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from blueprint_ai.main import create_app
from blueprint_ai.settings import Settings

ISSUER = "http://keycloak.test/realms/blueprint"
OLLAMA_URL = "http://ollama.test/v1"
OPENAI_URL = "https://openai.test/v1"

TokenFactory = Callable[..., str]


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def issue_token(signing_key: rsa.RSAPrivateKey) -> TokenFactory:
    def issue(
        roles: tuple[str, ...] = ("reader",),
        issuer: str = ISSUER,
        expires_in: int = 300,
        key: rsa.RSAPrivateKey | None = None,
    ) -> str:
        claims = {
            "sub": "user-1",
            "preferred_username": "reader",
            "iss": issuer,
            "exp": int(time.time()) + expires_in,
            "realm_access": {"roles": list(roles)},
        }
        return jwt.encode(claims, key or signing_key, algorithm="RS256")

    return issue


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        keycloak_issuer=ISSUER,
        ollama_base_url=OLLAMA_URL,
        ollama_models=["qwen3:8b"],
        openai_base_url=OPENAI_URL,
        openai_models=["gpt-5-mini"],
        openai_api_key="sk-test",
    )


@pytest.fixture
def client(settings: Settings, signing_key: rsa.RSAPrivateKey) -> Iterator[TestClient]:
    app = create_app(settings, resolve_key=lambda _token: signing_key.public_key())
    with TestClient(app) as test_client:
        yield test_client
