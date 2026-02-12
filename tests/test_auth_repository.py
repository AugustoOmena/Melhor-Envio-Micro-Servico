from __future__ import annotations

from typing import Any, Mapping

import pytest

from auth_repository import AuthRepository
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


def test_auth_repository_calls_token_url_and_form_content_type() -> None:
    cfg = MelhorEnvioConfig(env="sandbox", client_id="cid", client_secret="cs")
    http = _FakeHttp(HttpResponse(status_code=200, headers={}, body={"access_token": "t"}, raw_body='{"access_token":"t"}'))
    repo = AuthRepository(http=http, config=cfg)

    out = repo.request_token({"grant_type": "client_credentials", "client_id": "cid", "client_secret": "cs"})

    assert out["access_token"] == "t"
    assert http.last is not None
    assert http.last["url"] == cfg.token_url
    assert http.last["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert isinstance(http.last["data"], (bytes, bytearray))


def test_auth_repository_raises_on_error_status() -> None:
    cfg = MelhorEnvioConfig(env="sandbox", client_id="cid", client_secret="cs")
    http = _FakeHttp(HttpResponse(status_code=401, headers={}, body={"message": "unauthorized"}, raw_body="unauthorized"))
    repo = AuthRepository(http=http, config=cfg)

    with pytest.raises(HttpClientError):
        repo.request_token({"grant_type": "client_credentials", "client_id": "cid", "client_secret": "cs"})

