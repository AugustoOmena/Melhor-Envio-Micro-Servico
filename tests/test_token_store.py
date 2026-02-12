from __future__ import annotations

import datetime as dt

from shared.token_store import MelhorEnvioTokenStore


class _FakeSupabase:
    def __init__(self) -> None:
        self.last_post: dict | None = None
        self.rows = []

    def get(self, path: str, *, query: str = "", headers=None):  # type: ignore[no-untyped-def]
        return self.rows

    def post(self, path: str, *, json_body, headers=None):  # type: ignore[no-untyped-def]
        self.last_post = {"path": path, "json_body": json_body, "headers": headers}
        return [json_body]


def test_upsert_from_token_response_computes_expires_at_delta() -> None:
    fake = _FakeSupabase()
    store = MelhorEnvioTokenStore(fake)  # type: ignore[arg-type]

    rec = store.upsert_from_token_response(
        subject="admin",
        env="sandbox",
        token_response={"access_token": "a", "refresh_token": "r", "token_type": "Bearer", "expires_in": 3600},
    )

    assert rec.access_token == "a"
    assert rec.refresh_token == "r"
    assert rec.token_type == "Bearer"
    assert rec.expires_at is not None
    assert rec.expires_at.tzinfo is not None


def test_get_parses_iso_expires_at() -> None:
    fake = _FakeSupabase()
    store = MelhorEnvioTokenStore(fake)  # type: ignore[arg-type]

    fake.rows = [
        {
            "subject": "admin",
            "env": "sandbox",
            "access_token": "a",
            "refresh_token": "r",
            "token_type": "Bearer",
            "scope": None,
            "expires_at": "2026-02-12T10:00:00+00:00",
        }
    ]

    rec = store.get(subject="admin", env="sandbox")
    assert rec is not None
    assert rec.expires_at == dt.datetime(2026, 2, 12, 10, 0, 0, tzinfo=dt.timezone.utc)

