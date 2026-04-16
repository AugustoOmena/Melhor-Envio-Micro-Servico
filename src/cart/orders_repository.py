"""Persist order fields via Supabase (PostgREST)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from shared.supabase import SupabaseRestClient


def _payer_as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            parsed: Any = json.loads(s)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


class OrdersRepository:
    def __init__(self, supabase: SupabaseRestClient) -> None:
        self._sb = supabase

    def get_payer_phone(self, *, order_id: UUID) -> str | None:
        query = f"?id=eq.{order_id}&select=payer&limit=1"
        rows: Any = self._sb.get("orders", query=query)
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        payer = _payer_as_dict(rows[0].get("payer"))
        if payer is None:
            return None
        raw_phone = payer.get("phone")
        if raw_phone is None:
            return None
        phone = str(raw_phone).strip()
        return phone or None

    def set_melhor_envio_order_id(self, *, order_id: UUID, melhor_envio_order_id: str) -> bool:
        query = f"?id=eq.{order_id}"
        rows: Any = self._sb.patch(
            "orders",
            query=query,
            json_body={"melhor_envio_order_id": melhor_envio_order_id},
            headers={"Prefer": "return=representation", "Content-Type": "application/json"},
        )
        return isinstance(rows, list) and len(rows) > 0
