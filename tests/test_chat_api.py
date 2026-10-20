import json

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from blueprint_ai.main import create_app
from blueprint_ai.settings import Settings
from tests.conftest import OLLAMA_URL, OPENAI_URL, TokenFactory

ANSWER = {"choices": [{"message": {"role": "assistant", "content": "Hallo!"}}]}
COMPLETION = {
    "model": "qwen3:8b",
    "stream": False,
    "messages": [{"role": "user", "content": "Hallo"}],
    "reasoning_effort": "none",
}


def post(client: TestClient, provider: str, body: dict, token: str | None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(f"/api/v1/providers/{provider}/chat/completions", json=body, headers=headers)


@respx.mock
def test_forwards_the_completion_to_ollama_without_credentials(
    client: TestClient, issue_token: TokenFactory
) -> None:
    upstream = respx.post(f"{OLLAMA_URL}/chat/completions").respond(200, json=ANSWER)

    response = post(client, "ollama", COMPLETION, issue_token())

    assert response.status_code == 200
    assert response.json() == ANSWER
    sent = upstream.calls.last.request
    assert json.loads(sent.content) == COMPLETION
    assert "authorization" not in sent.headers


@respx.mock
def test_adds_the_server_side_api_key_for_openai(
    client: TestClient, issue_token: TokenFactory
) -> None:
    upstream = respx.post(f"{OPENAI_URL}/chat/completions").respond(200, json=ANSWER)

    post(client, "openai", {**COMPLETION, "model": "gpt-5-mini"}, issue_token())

    assert upstream.calls.last.request.headers["authorization"] == "Bearer sk-test"


@respx.mock
def test_passes_provider_errors_through(client: TestClient, issue_token: TokenFactory) -> None:
    error = {"error": {"message": "Rate limit reached"}}
    respx.post(f"{OPENAI_URL}/chat/completions").respond(429, json=error)

    response = post(client, "openai", {**COMPLETION, "model": "gpt-5-mini"}, issue_token())

    assert response.status_code == 429
    assert response.json() == error


@pytest.mark.parametrize(
    ("failure", "status"),
    [(httpx.ConnectError("refused"), 502), (httpx.ReadTimeout("slow"), 504)],
)
@respx.mock
def test_reports_an_unavailable_provider(
    client: TestClient, issue_token: TokenFactory, failure: Exception, status: int
) -> None:
    respx.post(f"{OLLAMA_URL}/chat/completions").mock(side_effect=failure)

    response = post(client, "ollama", COMPLETION, issue_token())

    assert response.status_code == status
    assert "ollama" in response.json()["detail"]


def test_rejects_unknown_providers(client: TestClient, issue_token: TokenFactory) -> None:
    response = post(client, "anthropic", COMPLETION, issue_token())

    assert response.status_code == 404


def test_rejects_models_outside_the_allowlist(
    client: TestClient, issue_token: TokenFactory
) -> None:
    response = post(client, "openai", {**COMPLETION, "model": "o1-pro"}, issue_token())

    assert response.status_code == 400
    assert response.json()["detail"] == "Model 'o1-pro' is not allowed for provider 'openai'."


def test_rejects_streaming(client: TestClient, issue_token: TokenFactory) -> None:
    response = post(client, "ollama", {**COMPLETION, "stream": True}, issue_token())

    assert response.status_code == 422


class TestAuthentication:
    def test_requires_a_bearer_token(self, client: TestClient) -> None:
        response = post(client, "ollama", COMPLETION, token=None)

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    @pytest.mark.parametrize(
        "token_args",
        [
            {"expires_in": -60},
            {"issuer": "http://evil.test/realms/blueprint"},
            {"key": rsa.generate_private_key(public_exponent=65537, key_size=2048)},
        ],
        ids=["expired", "foreign-issuer", "foreign-signature"],
    )
    def test_rejects_invalid_tokens(
        self, client: TestClient, issue_token: TokenFactory, token_args: dict
    ) -> None:
        response = post(client, "ollama", COMPLETION, issue_token(**token_args))

        assert response.status_code == 401

    @pytest.mark.parametrize("role", ["reader", "writer", "admin"])
    @respx.mock
    def test_lets_every_blueprint_role_chat(
        self, client: TestClient, issue_token: TokenFactory, role: str
    ) -> None:
        respx.post(f"{OLLAMA_URL}/chat/completions").respond(200, json=ANSWER)

        response = post(client, "ollama", COMPLETION, issue_token(roles=(role,)))

        assert response.status_code == 200

    def test_refuses_users_without_a_blueprint_role(
        self, client: TestClient, issue_token: TokenFactory
    ) -> None:
        response = post(client, "ollama", COMPLETION, issue_token(roles=("offline_access",)))

        assert response.status_code == 403


def test_reports_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "UP"}


def test_reports_unreachable_token_keys(settings: Settings, issue_token: TokenFactory) -> None:
    def unreachable(_token: str) -> None:
        raise jwt.PyJWKClientConnectionError("keycloak down")

    with TestClient(create_app(settings, resolve_key=unreachable)) as client:
        response = post(client, "ollama", COMPLETION, issue_token())

    assert response.status_code == 503
