"""Persist order fields via Supabase (PostgREST).

Colunas de orders usadas aqui: id, payer, melhor_envio_order_id (ver sql/01_init_schema.sql).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from uuid import UUID

from shared.supabase import SupabaseRestClient


@dataclass(frozen=True)
class PayerPhoneLookup:
    phone: str | None
    payer_state: str
    resolved_order_id: UUID | None = None


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


def _postgrest_eq_filter(column: str, raw_value: str) -> str:
    return f"?{column}=eq.{quote(raw_value, safe='')}&select=id,payer&limit=1"


def _resolved_uuid(row: dict[str, Any]) -> UUID | None:
    raw = row.get("id")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


class OrdersRepository:
    def __init__(self, supabase: SupabaseRestClient) -> None:
        self._sb = supabase

    def _payer_lookup_from_row(self, row: dict[str, Any]) -> PayerPhoneLookup:
        resolved = _resolved_uuid(row)
        raw_payer = row.get("payer")
        if raw_payer is None:
            return PayerPhoneLookup(None, "payer_column_null", resolved)
        payer = _payer_as_dict(raw_payer)
        if payer is None:
            return PayerPhoneLookup(None, "payer_not_json_object", resolved)
        raw_phone = payer.get("phone")
        if raw_phone is None:
            raw_phone = payer.get("Phone")
        if raw_phone is None:
            return PayerPhoneLookup(None, "payer_dict_without_phone", resolved)
        phone = str(raw_phone).strip()
        if not phone:
            return PayerPhoneLookup(None, "payer_phone_blank", resolved)
        return PayerPhoneLookup(phone, "phone_ok", resolved)

    def lookup_payer_phone(
        self,
        *,
        order_id: UUID | None = None,
        mp_payment_id: str | None = None,
        payment_id: str | None = None,
    ) -> PayerPhoneLookup | None:
        if order_id is not None:
            query = f"?id=eq.{order_id}&select=id,payer&limit=1"
        elif mp_payment_id:
            query = _postgrest_eq_filter("mp_payment_id", mp_payment_id)
        elif payment_id:
            query = _postgrest_eq_filter("payment_id", payment_id)
        else:
            return None
        rows: Any = self._sb.get("orders", query=query)
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return PayerPhoneLookup(None, "no_order_row", None)
        return self._payer_lookup_from_row(rows[0])

    def get_payer_phone(self, *, order_id: UUID) -> str | None:
        got = self.lookup_payer_phone(order_id=order_id)
        return got.phone if got else None

    def _order_has_melhor_envio_id(self, *, order_id: UUID, expected: str) -> bool:
        query = f"?id=eq.{order_id}&select=melhor_envio_order_id&limit=1"
        rows: Any = self._sb.get("orders", query=query)
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return False
        got = rows[0].get("melhor_envio_order_id")
        return str(got) == str(expected)

    def set_melhor_envio_order_id(self, *, order_id: UUID, melhor_envio_order_id: str) -> bool:
        query = f"?id=eq.{order_id}"
        rows: Any = self._sb.patch(
            "orders",
            query=query,
            json_body={"melhor_envio_order_id": melhor_envio_order_id},
            headers={"Prefer": "return=representation", "Content-Type": "application/json"},
        )
        if isinstance(rows, list) and len(rows) > 0:
            return True
        return self._order_has_melhor_envio_id(order_id=order_id, expected=melhor_envio_order_id)
