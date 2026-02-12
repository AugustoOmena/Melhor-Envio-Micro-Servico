"""Business logic for Melhor Envio OAuth token operations."""

from __future__ import annotations

from typing import Any

from auth_schemas import TokenRequest
from shared.melhor_envio_oauth import MelhorEnvioOAuthClient


class AuthService:
    def __init__(self, oauth: MelhorEnvioOAuthClient, *, client_id: str, client_secret: str) -> None:
        self._oauth = oauth
        self._client_id = client_id
        self._client_secret = client_secret

    def create_token(self, req: TokenRequest) -> dict[str, Any]:
        payload: dict[str, str] = {
            "grant_type": req.grant_type,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if req.scope:
            payload["scope"] = req.scope
        if req.grant_type == "authorization_code":
            payload["code"] = req.code or ""
            payload["redirect_uri"] = req.redirect_uri or ""
        if req.grant_type == "refresh_token":
            payload["refresh_token"] = req.refresh_token or ""

        return self._oauth.request_token(payload)

