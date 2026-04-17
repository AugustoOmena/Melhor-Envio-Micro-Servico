from __future__ import annotations

from uuid import UUID

from cart_schemas import InsertCartPayload


def test_insert_cart_payload_excludes_order_id_from_me_body() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    req = InsertCartPayload.model_validate(
        {
            "service": 1,
            "from": {"name": "A", "address": "x", "number": "1", "district": "d", "city": "c", "postal_code": "123", "state_abbr": "SP"},
            "to": {"name": "B", "address": "y", "number": "2", "district": "d", "city": "c", "postal_code": "456", "state_abbr": "RJ"},
            "products": [{"name": "P", "quantity": "1", "unitary_value": "10"}],
            "order_id": str(oid),
        }
    )
    body = req.model_dump(by_alias=True, exclude_none=False, exclude={"order_id"})
    assert "order_id" not in body
    assert req.order_id == oid
