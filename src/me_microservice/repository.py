from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class MelhorEnvioApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True, slots=True)
class MelhorEnvioRepository:
    base_url: str
    timeout_seconds: float
    user_agent: str

    def exchange_token(self, data: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}/oauth/token"
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(url, data=data, headers=headers, timeout=self.timeout_seconds)
        return self._parse_response(response)

    def insert_cart(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/api/v2/me/cart"
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: requests.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text}

        if 200 <= response.status_code < 300:
            if isinstance(body, dict):
                return body
            return {"data": body}

        message = "Melhor Envio API request failed"
        if isinstance(body, dict) and body.get("message"):
            message = str(body["message"])

        raise MelhorEnvioApiError(status_code=response.status_code, message=message, payload=body)
