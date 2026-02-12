from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from repository import MelhorEnvioRepository
from settings import Settings


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MelhorEnvioService:
    settings: Settings
    repository: MelhorEnvioRepository

    def build_authorize_url(
        self,
        *,
        redirect_uri: str,
        scope: str | None,
        state: str | None,
    ) -> str:
        client_id = self.settings.melhor_envio_client_id
        if not client_id:
            raise ConfigurationError("Missing MELHOR_ENVIO_CLIENT_ID")

        query: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
        }

        resolved_scope = scope or self.settings.melhor_envio_default_scope
        if resolved_scope:
            query["scope"] = resolved_scope
        if state:
            query["state"] = state

        return f"{self.settings.melhor_envio_base_url}/oauth/authorize?{urlencode(query)}"

    def exchange_token(self, *, grant_type: str, redirect_uri: str | None, code: str | None) -> dict[str, Any]:
        client_id = self.settings.melhor_envio_client_id
        client_secret = self.settings.melhor_envio_client_secret
        if not client_id or not client_secret:
            raise ConfigurationError("Missing MELHOR_ENVIO_CLIENT_ID or MELHOR_ENVIO_CLIENT_SECRET")

        data: dict[str, str] = {
            "grant_type": grant_type,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
        if code:
            data["code"] = code

        return self.repository.exchange_token(data=data)

    def refresh_token(self, *, refresh_token: str) -> dict[str, Any]:
        client_id = self.settings.melhor_envio_client_id
        client_secret = self.settings.melhor_envio_client_secret
        if not client_id or not client_secret:
            raise ConfigurationError("Missing MELHOR_ENVIO_CLIENT_ID or MELHOR_ENVIO_CLIENT_SECRET")

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        return self.repository.exchange_token(data=data)

    def insert_cart(self, *, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.repository.insert_cart(access_token=access_token, payload=payload)
