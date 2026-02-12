from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings sourced from environment variables."""

    melhor_envio_base_url: str
    melhor_envio_client_id: str | None
    melhor_envio_client_secret: str | None
    melhor_envio_default_scope: str | None
    http_timeout_seconds: float
    user_agent: str


def get_settings() -> Settings:
    """Build settings from environment variables."""
    timeout_raw = getenv("HTTP_TIMEOUT_SECONDS", "15")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 15.0

    return Settings(
        melhor_envio_base_url=getenv("MELHOR_ENVIO_BASE_URL", "https://sandbox.melhorenvio.com.br").rstrip(
            "/"
        ),
        melhor_envio_client_id=getenv("MELHOR_ENVIO_CLIENT_ID"),
        melhor_envio_client_secret=getenv("MELHOR_ENVIO_CLIENT_SECRET"),
        melhor_envio_default_scope=getenv("MELHOR_ENVIO_DEFAULT_SCOPE"),
        http_timeout_seconds=timeout,
        user_agent=getenv("USER_AGENT", "me-microservice/1.0"),
    )
