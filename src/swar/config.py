"""Settings loaded from environment variables and `.env`.

Every key is optional at import time, so tests and tools that don't need a provider
still run. Code that needs a key should call `require()` to get a clear error.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Speech-to-text / text-to-speech providers (D-008)
    sarvam_api_key: SecretStr | None = None
    deepgram_api_key: SecretStr | None = None
    cartesia_api_key: SecretStr | None = None

    # LLMs (D-008)
    google_api_key: SecretStr | None = None

    # Infrastructure (infra/docker-compose.yml)
    database_url: str = "postgresql+asyncpg://swar:swar@localhost:5432/swar"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    def require(self, name: str) -> str:
        """Return the secret value of `name`, or raise a clear error if it isn't set."""
        value = getattr(self, name)
        if value is None:
            raise RuntimeError(f"{name.upper()} is not set. Add it to .env (see .env.example).")
        return value.get_secret_value() if isinstance(value, SecretStr) else str(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
