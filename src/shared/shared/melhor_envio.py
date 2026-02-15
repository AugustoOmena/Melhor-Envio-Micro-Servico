"""Melhor Envio API configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

import urllib.parse


@dataclass(frozen=True)
class MelhorEnvioConfig:
    env: str
    client_id: str | None
    client_secret: str | None
    default_redirect_uri: str | None = None
    default_scopes: tuple[str, ...] = ()

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
    def authorize_url_base(self) -> str:
        return f"{self.base_url}/oauth/authorize"

    @property
    def cart_url(self) -> str:
        return f"{self.base_url}/api/v2/me/cart"

    def build_authorize_url(
        self,
        *,
        redirect_uri: str,
        scopes: Sequence[str],
        state: str,
        response_type: str = "code",
    ) -> str:
        # Melhor Envio espera scope como string única com escopos separados por espaço (ex: scope=cart%20shipment%20tracking).
        scope_str = " ".join(scopes) if scopes else ""
        query = urllib.parse.urlencode(
            {
                "response_type": response_type,
                "client_id": self.client_id or "",
                "redirect_uri": redirect_uri,
                "scope": scope_str,
                "state": state,
            }
        )
        return f"{self.authorize_url_base}?{query}"


def load_config() -> MelhorEnvioConfig:
    scopes_raw = os.getenv("MELHOR_ENVIO_SCOPES", "").strip()
    scopes = tuple([s.strip() for s in scopes_raw.split(",") if s.strip()]) if scopes_raw else ()
    return MelhorEnvioConfig(
        env=os.getenv("MELHOR_ENVIO_ENV", "sandbox"),
        client_id=os.getenv("MELHOR_ENVIO_CLIENT_ID"),
        client_secret=os.getenv("MELHOR_ENVIO_CLIENT_SECRET"),
        default_redirect_uri=os.getenv("MELHOR_ENVIO_REDIRECT_URI"),
        default_scopes=scopes,
    )

