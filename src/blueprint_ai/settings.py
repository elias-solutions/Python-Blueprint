from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keycloak_issuer: str = "http://localhost:8180/realms/blueprint"
    keycloak_jwks_url: str | None = None

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_models: list[str] = ["qwen3:8b"]

    openai_base_url: str = "https://api.openai.com/v1"
    openai_models: list[str] = ["gpt-5-mini", "gpt-5"]
    openai_api_key: SecretStr | None = None

    upstream_timeout_seconds: float = 180

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def blank_key_is_missing(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def jwks_url(self) -> str:
        return self.keycloak_jwks_url or f"{self.keycloak_issuer}/protocol/openid-connect/certs"
