from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel, field_validator


class AuthorizeUrlRequest(BaseModel):
    client_id: str | None = Field(default=None, description="Overrides env var if provided.")
    redirect_uri: str = Field(..., min_length=1)
    scope: str | None = None
    state: str | None = None


class AuthorizeUrlResponse(BaseModel):
    url: str


GrantType = Literal["authorization_code", "refresh_token"]


class TokenRequest(BaseModel):
    grant_type: GrantType = "authorization_code"
    redirect_uri: str | None = None
    code: str | None = None
    refresh_token: str | None = None

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("refresh_token")
    @classmethod
    def _strip_refresh_token(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("redirect_uri")
    @classmethod
    def _strip_redirect_uri(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @field_validator("grant_type")
    @classmethod
    def _validate_required_fields(cls, v: GrantType, info):  # type: ignore[no-untyped-def]
        data = info.data
        if v == "authorization_code":
            if not data.get("code") or not data.get("redirect_uri"):
                raise ValueError("grant_type=authorization_code requires code and redirect_uri")
        if v == "refresh_token":
            if not data.get("refresh_token"):
                raise ValueError("grant_type=refresh_token requires refresh_token")
        return v


class TokenResponse(RootModel[dict[str, Any]]):
    """Proxy response from Melhor Envio OAuth token endpoint."""


class InsertCartRequest(RootModel[dict[str, Any]]):
    @field_validator("root")
    @classmethod
    def _non_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("Request body must be a non-empty JSON object.")
        return v


class InsertCartResponse(RootModel[dict[str, Any]]):
    """Proxy response from Melhor Envio 'Inserir fretes no carrinho' endpoint."""

