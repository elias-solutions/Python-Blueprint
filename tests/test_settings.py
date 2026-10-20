import pytest

from blueprint_ai.settings import Settings


@pytest.mark.parametrize("value", ["", "   "])
def test_treats_a_blank_api_key_as_missing(value: str) -> None:
    assert Settings(_env_file=None, openai_api_key=value).openai_api_key is None


def test_keeps_a_real_api_key() -> None:
    settings = Settings(_env_file=None, openai_api_key="sk-test")

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-test"
