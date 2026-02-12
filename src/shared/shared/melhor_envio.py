"""Melhor Envio API configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MelhorEnvioConfig:
    env: str
    client_id: str | None
    client_secret: str | None

    @property
    def base_url(self) -> str:
        # Docs use sandbox URLs; production uses melhorenvio.com.br.
        if self.env.lower() == "production":
            return "https://melhorenvio.com.br"
        return "https://sandbox.melhorenvio.com.br"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/oauth/token"

    @property
    def cart_url(self) -> str:
        return f"{self.base_url}/api/v2/me/cart"


def load_config() -> MelhorEnvioConfig:
    return MelhorEnvioConfig(
        env=os.getenv("MELHOR_ENVIO_ENV", "sandbox"),
        client_id=os.getenv("MELHOR_ENVIO_CLIENT_ID"),
        client_secret=os.getenv("MELHOR_ENVIO_CLIENT_SECRET"),
    )

