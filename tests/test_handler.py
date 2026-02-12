from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

import handler
from repository import MelhorEnvioApiError


def _event(method: str, path: str, *, body: dict | None = None, headers: dict | None = None) -> dict:
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers or {},
        "requestContext": {
            "stage": "$default",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            }
        },
        "isBase64Encoded": False,
        "body": None if body is None else json.dumps(body),
    }


def test_health_ok() -> None:
    resp = handler.lambda_handler(_event("GET", "/health"), context=Mock())
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"status": "ok"}


def test_me_cart_requires_bearer_token() -> None:
    resp = handler.lambda_handler(_event("POST", "/me/cart", body={"x": 1}), context=Mock())
    assert resp["statusCode"] == 401


def test_me_cart_proxies_error_status_code() -> None:
    fake_service = Mock()
    fake_service.insert_cart.side_effect = MelhorEnvioApiError(403, "forbidden", payload={"message": "forbidden"})

    with patch.object(handler, "_get_service", return_value=fake_service):
        resp = handler.lambda_handler(
            _event(
                "POST",
                "/me/cart",
                body={"foo": "bar"},
                headers={"authorization": "Bearer token"},
            ),
            context=Mock(),
        )

    assert resp["statusCode"] == 403
    assert json.loads(resp["body"]) == {"message": "forbidden"}


def test_auth_authorize_url_returns_200() -> None:
    fake_service = Mock()
    fake_service.build_authorize_url.return_value = "https://sandbox.melhorenvio.com.br/oauth/authorize?x=y"

    with patch.object(handler, "_get_service", return_value=fake_service):
        resp = handler.lambda_handler(
            _event("POST", "/auth/authorize-url", body={"redirect_uri": "https://example.com/cb"}),
            context=Mock(),
        )

    assert resp["statusCode"] == 200
    assert "url" in json.loads(resp["body"])

