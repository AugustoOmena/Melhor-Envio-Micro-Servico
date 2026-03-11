"""Repository responsible for calling Melhor Envio cart endpoints."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def _json_default(obj: Any) -> Any:
    """Decimal não é serializável por json.dumps; API espera number."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

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
        # Payload já validado em InsertCartPayload; sem recálculo. Decimal→float se necessário.
        serializable = payload
        try:
            json.dumps(payload, ensure_ascii=False)
        except TypeError:
            serializable = json.loads(json.dumps(payload, default=_json_default, ensure_ascii=False))

        resp = self._http.request_json(
            "POST",
            self._config.cart_url,
            headers=headers,
            json_body=serializable,
        )
        if resp.status_code >= 400:
            raise HttpClientError(resp.status_code, "Cart insert failed", response_body=resp.raw_body)
        return resp.status_code, resp.body

