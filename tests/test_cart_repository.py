from __future__ import annotations

from typing import Any, Mapping

import pytest

from cart_repository import CartRepository
from shared.http import HttpClientError, HttpResponse
from shared.melhor_envio import MelhorEnvioConfig


class _FakeHttp:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.last: dict[str, Any] | None = None

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        self.last = {"method": method, "url": url, "headers": dict(headers or {}), "json_body": json_body, "data": data}
        return self.response


def test_cart_repository_calls_cart_url() -> None:
    cfg = MelhorEnvioConfig(env="sandbox", client_id=None, client_secret=None)
    http = _FakeHttp(HttpResponse(status_code=200, headers={}, body={"id": 1}, raw_body='{"id":1}'))
    repo = CartRepository(http=http, config=cfg)

    status, body = repo.insert_cart(authorization="Bearer t", payload={"a": 1})

    assert status == 200
    assert body == {"id": 1}
    assert http.last is not None
    assert http.last["url"] == cfg.cart_url
    assert http.last["headers"]["Authorization"] == "Bearer t"


def test_cart_repository_raises_on_error_status() -> None:
    cfg = MelhorEnvioConfig(env="sandbox", client_id=None, client_secret=None)
    http = _FakeHttp(HttpResponse(status_code=400, headers={}, body={"error": "bad"}, raw_body='{"error":"bad"}'))
    repo = CartRepository(http=http, config=cfg)

    with pytest.raises(HttpClientError):
        repo.insert_cart(authorization="Bearer t", payload={"a": 1})

