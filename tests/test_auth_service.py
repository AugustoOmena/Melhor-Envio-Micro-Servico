from __future__ import annotations

from typing import Any

from auth_schemas import TokenRequest
from auth_service import AuthService


class _FakeRepo:
    def __init__(self) -> None:
        self.last_payload: dict[str, str] | None = None

    def request_token(self, payload: dict[str, str]) -> dict[str, Any]:
        self.last_payload = payload
        return {"access_token": "x", "token_type": "Bearer"}


def test_auth_service_builds_payload_for_authorization_code() -> None:
    repo = _FakeRepo()
    svc = AuthService(repo=repo, client_id="cid", client_secret="csecret")

    req = TokenRequest.model_validate(
        {"grant_type": "authorization_code", "code": "abc", "redirect_uri": "https://example.com/callback"}
    )
    out = svc.create_token(req)

    assert out["access_token"] == "x"
    assert repo.last_payload is not None
    assert repo.last_payload["grant_type"] == "authorization_code"
    assert repo.last_payload["client_id"] == "cid"
    assert repo.last_payload["client_secret"] == "csecret"
    assert repo.last_payload["code"] == "abc"
    assert repo.last_payload["redirect_uri"] == "https://example.com/callback"


def test_auth_service_builds_payload_for_refresh_token() -> None:
    repo = _FakeRepo()
    svc = AuthService(repo=repo, client_id="cid", client_secret="csecret")

    req = TokenRequest.model_validate({"grant_type": "refresh_token", "refresh_token": "r1"})
    svc.create_token(req)

    assert repo.last_payload is not None
    assert repo.last_payload["grant_type"] == "refresh_token"
    assert repo.last_payload["refresh_token"] == "r1"

