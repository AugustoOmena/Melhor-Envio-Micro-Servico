"""Persist order fields via Supabase (PostgREST)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.supabase import SupabaseRestClient


class OrdersRepository:
    def __init__(self, supabase: SupabaseRestClient) -> None:
        self._sb = supabase

    def set_melhor_envio_order_id(self, *, order_id: UUID, melhor_envio_order_id: str) -> bool:
        query = f"?id=eq.{order_id}"
        rows: Any = self._sb.patch(
            "orders",
            query=query,
            json_body={"melhor_envio_order_id": melhor_envio_order_id},
            headers={"Prefer": "return=representation", "Content-Type": "application/json"},
        )
        return isinstance(rows, list) and len(rows) > 0
