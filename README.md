# Python-Blueprint – KI-Gateway

FastAPI-Service, über den der KI-Assistent von `Angular-Blueprint` mit den Sprachmodellen spricht.
Er leitet OpenAI-kompatible Chat-Completions an **Ollama** (lokal) oder **OpenAI** weiter. Der
OpenAI-Key liegt nur hier auf dem Server und erreicht nie den Browser.

## Endpunkt

`POST /api/v1/providers/{provider}/chat/completions` – Body im OpenAI-Format (`stream: false`).

| provider | Ziel | Key | erlaubte Modelle (Default) |
|---|---|---|---|
| `ollama` | `OLLAMA_BASE_URL` (http://localhost:11434/v1) | – | `qwen3:8b` |
| `openai` | `OPENAI_BASE_URL` (https://api.openai.com/v1) | `OPENAI_API_KEY` | `gpt-5-mini`, `gpt-5` |

- **Auth:** Bearer-Token aus dem Keycloak-Realm `blueprint` (Signatur über JWKS, `exp`, `iss`).
  Jede Blueprint-Rolle (`reader`, `writer`, `admin`) darf chatten, sonst 403.
- **Allowlist:** Nur die konfigurierten Modelle werden weitergeleitet (400 sonst) – schützt vor
  teuren Modellen.
- Antworten und Fehler des Providers (z.B. 401, 429) werden unverändert durchgereicht; Provider
  nicht erreichbar → 502, Timeout → 504.
- `GET /health` → `{"status": "UP"}`, Swagger unter `/docs`.

## Konfiguration (Umgebungsvariablen)

| Variable | Default |
|---|---|
| `OPENAI_API_KEY` | – (ohne Key antwortet OpenAI mit 401) |
| `OPENAI_MODELS` | `["gpt-5-mini","gpt-5"]` (JSON-Liste) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `OLLAMA_MODELS` | `["qwen3:8b"]` |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` |
| `KEYCLOAK_ISSUER` | `http://localhost:8180/realms/blueprint` |
| `KEYCLOAK_JWKS_URL` | `<KEYCLOAK_ISSUER>/protocol/openid-connect/certs` |
| `UPSTREAM_TIMEOUT_SECONDS` | `180` |

Im Container setzt `Init-Blueprint/docker-compose.yml` die Werte; der Key kommt aus
`Init-Blueprint/.env`. Lokal ohne Docker werden sie zusätzlich aus einer `.env` in diesem Ordner
gelesen (git-ignoriert, z.B. `OPENAI_API_KEY=sk-…`).

## Entwickeln

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/python -m uvicorn blueprint_ai.main:create_app --factory --port 5300 --reload
```

## Architektur

```
src/blueprint_ai/
  main.py          create_app(): Settings, Registry, TokenVerifier, httpx-Client (Lifespan)
  settings.py      Konfiguration aus Umgebung/.env (pydantic-settings)
  upstreams.py     Upstream (Ziel, Modell-Allowlist, Key) + UpstreamRegistry
  forwarder.py     ChatForwarder: leitet an den Upstream weiter, Transportfehler → 502/504
  auth.py          TokenVerifier (Keycloak-JWT) + Dependency require_chat_user
  chat_router.py   POST /api/v1/providers/{provider}/chat/completions
tests/             Integrationstests über TestClient; Provider per respx gemockt
```
