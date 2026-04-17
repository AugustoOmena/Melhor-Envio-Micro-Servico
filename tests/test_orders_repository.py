from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import UUID

from orders_repository import OrdersRepository
from shared.http import HttpResponse
from shared.supabase import SupabaseConfig, SupabaseRestClient


class _FakeHttp:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
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
        if not self._responses:
            return HttpResponse(status_code=200, headers={}, body=[], raw_body="[]")
        return self._responses.pop(0)


def test_set_melhor_envio_order_id_true_when_row_returned() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    http = _FakeHttp([HttpResponse(status_code=200, headers={}, body=[{"id": str(oid), "melhor_envio_order_id": "me-1"}], raw_body="[]")])
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.set_melhor_envio_order_id(order_id=oid, melhor_envio_order_id="me-1") is True
    assert http.calls[0]["method"] == "PATCH"
    assert "orders" in http.calls[0]["url"]
    assert http.calls[0]["json_body"] == {"melhor_envio_order_id": "me-1"}


def test_set_melhor_envio_order_id_true_when_patch_empty_body_but_get_confirms() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    verify_body = [{"melhor_envio_order_id": "me-1"}]
    http = _FakeHttp(
        [
            HttpResponse(status_code=200, headers={}, body=None, raw_body=""),
            HttpResponse(status_code=200, headers={}, body=verify_body, raw_body=json.dumps(verify_body)),
        ]
    )
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.set_melhor_envio_order_id(order_id=oid, melhor_envio_order_id="me-1") is True
    assert http.calls[0]["method"] == "PATCH"
    assert http.calls[1]["method"] == "GET"


def test_set_melhor_envio_order_id_false_when_empty() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    verify_body: list[dict[str, Any]] = [{"melhor_envio_order_id": None}]
    http = _FakeHttp(
        [
            HttpResponse(status_code=200, headers={}, body=[], raw_body="[]"),
            HttpResponse(status_code=200, headers={}, body=verify_body, raw_body=json.dumps(verify_body)),
        ]
    )
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.set_melhor_envio_order_id(order_id=oid, melhor_envio_order_id="me-1") is False


def test_get_payer_phone_returns_phone_from_json() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    body = [{"payer": {"email": "x@y.com", "phone": "24981021079"}}]
    http = _FakeHttp([HttpResponse(status_code=200, headers={}, body=body, raw_body=json.dumps(body))])
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.get_payer_phone(order_id=oid) == "24981021079"
    assert http.calls[0]["method"] == "GET"


def test_get_payer_phone_returns_none_when_missing() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    body = [{"payer": {"email": "x@y.com"}}]
    http = _FakeHttp([HttpResponse(status_code=200, headers={}, body=body, raw_body=json.dumps(body))])
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.get_payer_phone(order_id=oid) is None


def test_get_payer_phone_parses_payer_json_string() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    payer_json = '{"email":"x@y.com","phone":"24981021079"}'
    body = [{"payer": payer_json}]
    http = _FakeHttp([HttpResponse(status_code=200, headers={}, body=body, raw_body=json.dumps(body))])
    sb = SupabaseRestClient(
        http=http,
        cfg=SupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    repo = OrdersRepository(sb)
    assert repo.get_payer_phone(order_id=oid) == "24981021079"
