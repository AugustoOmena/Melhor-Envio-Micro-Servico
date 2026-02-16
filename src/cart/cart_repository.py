"""Repository responsible for calling Melhor Envio cart endpoints."""

from __future__ import annotations

from typing import Any

from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import MelhorEnvioConfig


class CartRepository:
    def __init__(self, http: HttpClient, config: MelhorEnvioConfig, *, user_agent: str | None = None) -> None:
        self._http = http
        self._config = config
        self._user_agent = user_agent or "MelhorEnvio-Integration (contato@example.com)"

    def insert_cart(self, *, authorization: str, payload: Any) -> tuple[int, Any]:
        headers = {
            "Authorization": authorization,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
        }
        resp = self._http.request_json(
            "POST",
            self._config.cart_url,
            headers=headers,
            json_body=payload,
        )
        if resp.status_code >= 400:
            raise HttpClientError(resp.status_code, "Cart insert failed", response_body=resp.raw_body)
        return resp.status_code, resp.body

