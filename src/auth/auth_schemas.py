"""Schemas (DTOs) for the auth Lambda."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TokenRequest(BaseModel):
    """Request for exchanging/refreshing a Melhor Envio OAuth token."""

    model_config = ConfigDict(extra="forbid")

    grant_type: Literal["authorization_code", "refresh_token", "client_credentials"] = Field(
        description="OAuth 2.0 grant type supported by Melhor Envio."
    )
    code: str | None = Field(default=None, description="Authorization code (authorization_code flow).")
    redirect_uri: str | None = Field(default=None, description="Redirect URI used to obtain the code.")
    refresh_token: str | None = Field(default=None, description="Refresh token (refresh_token flow).")
    scope: str | None = Field(default=None, description="Optional scopes (if required by the grant).")

    @model_validator(mode="after")
    def _validate_flow(self) -> "TokenRequest":
        if self.grant_type == "authorization_code":
            if not self.code or not self.redirect_uri:
                raise ValueError("code and redirect_uri are required for authorization_code grant_type.")
        if self.grant_type == "refresh_token":
            if not self.refresh_token:
                raise ValueError("refresh_token is required for refresh_token grant_type.")
        return self


class TokenResponse(BaseModel):
    """Normalized token response."""

    model_config = ConfigDict(extra="allow")

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    raw: Any | None = None

