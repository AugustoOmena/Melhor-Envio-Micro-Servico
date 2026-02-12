from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from schemas import (
    AuthorizeUrlRequest,
    AuthorizeUrlResponse,
    InsertCartRequest,
    InsertCartResponse,
    TokenRequest,
    TokenResponse,
)
from service import MelhorEnvioService


class BadRequestError(RuntimeError):
    pass


def build_authorize_url(service: MelhorEnvioService, body: dict[str, Any]) -> dict[str, Any]:
    try:
        req = AuthorizeUrlRequest.model_validate(body)
    except ValidationError as exc:
        raise BadRequestError(str(exc)) from exc

    url = service.build_authorize_url(redirect_uri=req.redirect_uri, scope=req.scope, state=req.state)
    return AuthorizeUrlResponse(url=url).model_dump()


def request_token(service: MelhorEnvioService, body: dict[str, Any]) -> dict[str, Any]:
    try:
        req = TokenRequest.model_validate(body)
    except ValidationError as exc:
        raise BadRequestError(str(exc)) from exc

    payload = service.exchange_token(grant_type=req.grant_type, redirect_uri=req.redirect_uri, code=req.code)
    return TokenResponse(payload).model_dump(mode="json")


def refresh_token(service: MelhorEnvioService, body: dict[str, Any]) -> dict[str, Any]:
    try:
        req = TokenRequest.model_validate({**body, "grant_type": "refresh_token"})
    except ValidationError as exc:
        raise BadRequestError(str(exc)) from exc

    if not req.refresh_token:
        raise BadRequestError("refresh_token is required")

    payload = service.refresh_token(refresh_token=req.refresh_token)
    return TokenResponse(payload).model_dump(mode="json")


def insert_cart(service: MelhorEnvioService, access_token: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        req = InsertCartRequest.model_validate(body)
    except ValidationError as exc:
        raise BadRequestError(str(exc)) from exc

    payload = service.insert_cart(access_token=access_token, payload=req.root)
    return InsertCartResponse(payload).model_dump(mode="json")

