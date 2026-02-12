"""Melhor Envio OAuth operations shared across Lambdas."""

from __future__ import annotations

import urllib.parse
from typing import Any

from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import MelhorEnvioConfig


class MelhorEnvioOAuthClient:
    def __init__(self, http: HttpClient, config: MelhorEnvioConfig) -> None:
        self._http = http
        self._config = config

    def request_token(self, payload: dict[str, str]) -> dict[str, Any]:
        data = urllib.parse.urlencode(payload, doseq=True).encode("utf-8")
        resp = self._http.request_json(
            "POST",
            self._config.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data=data,
        )
        if resp.status_code >= 400:
            raise HttpClientError(resp.status_code, "Token request failed", response_body=resp.raw_body)
        if not isinstance(resp.body, dict):
            raise HttpClientError(resp.status_code, "Unexpected token response", response_body=resp.raw_body)
        return resp.body

