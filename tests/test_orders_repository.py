from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from orders_repository import OrdersRepository
from shared.http import HttpResponse
from shared.supabase import SupabaseConfig, SupabaseRestClient


class _FakeHttp:
    def __init__(self, bodies: list[Any]) -> None:
        self._bodies = bodies
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        self.calls.append({"method": method, "url": url, "json_body": json_body})
        body = self._bodies.pop(0) if self._bodies else []
        return HttpResponse(status_code=200, headers={}, body=body, raw_body="[]")


def test_set_melhor_envio_order_id_true_when_row_returned() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    http = _FakeHttp([[{"id": str(oid), "melhor_envio_order_id": "me-1"}]])
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.set_melhor_envio_order_id(order_id=oid, melhor_envio_order_id="me-1") is True
    assert http.calls[0]["method"] == "PATCH"
    assert "orders" in http.calls[0]["url"]
    assert http.calls[0]["json_body"] == {"melhor_envio_order_id": "me-1"}


def test_set_melhor_envio_order_id_false_when_empty() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    http = _FakeHttp([[]])
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.set_melhor_envio_order_id(order_id=oid, melhor_envio_order_id="me-1") is False
