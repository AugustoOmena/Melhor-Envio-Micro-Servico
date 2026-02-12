from __future__ import annotations

from typing import Any

from cart_service import CartService


class _FakeRepo:
    def __init__(self) -> None:
        self.last_auth: str | None = None
        self.last_payload: Any | None = None

    def insert_cart(self, *, authorization: str, payload: Any) -> tuple[int, Any]:
        self.last_auth = authorization
        self.last_payload = payload
        return 200, {"ok": True}


def test_cart_service_forwards_authorization_and_payload() -> None:
    repo = _FakeRepo()
    svc = CartService(repo=repo)

    status, body = svc.insert_freights(authorization="Bearer t", payload={"x": 1})

    assert status == 200
    assert body == {"ok": True}
    assert repo.last_auth == "Bearer t"
    assert repo.last_payload == {"x": 1}

