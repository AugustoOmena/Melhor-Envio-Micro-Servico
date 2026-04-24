from __future__ import annotations

from uuid import UUID

import pytest
from cart_schemas import InsertCartPayload
from pydantic import ValidationError


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
    body = req.model_dump(by_alias=True, exclude_none=False, exclude={"order_id", "mp_payment_id", "payment_id"})
    assert "order_id" not in body
    assert req.order_id == oid


def test_insert_cart_payload_excludes_payment_correlation_from_me_body() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    req = InsertCartPayload.model_validate(
        {
            "service": 1,
            "from": {"name": "A", "address": "x", "number": "1", "district": "d", "city": "c", "postal_code": "123", "state_abbr": "SP"},
            "to": {"name": "B", "address": "y", "number": "2", "district": "d", "city": "c", "postal_code": "456", "state_abbr": "RJ"},
            "products": [{"name": "P", "quantity": "1", "unitary_value": "10"}],
            "order_id": str(oid),
            "mpPaymentId": "123456789",
        }
    )
    body = req.model_dump(by_alias=True, exclude_none=False, exclude={"order_id", "mp_payment_id", "payment_id"})
    assert "order_id" not in body
    assert "mp_payment_id" not in body
    assert "mpPaymentId" not in body


def test_insert_cart_payload_rejects_invalid_option_booleans() -> None:
    with pytest.raises(ValidationError):
        InsertCartPayload.model_validate(
            {
                "service": 1,
                "from": {"name": "A", "address": "x", "number": "1", "district": "d", "city": "c", "postal_code": "123", "state_abbr": "SP"},
                "to": {"name": "B", "address": "y", "number": "2", "district": "d", "city": "c", "postal_code": "456", "state_abbr": "RJ"},
                "products": [{"name": "P", "quantity": "1", "unitary_value": "10"}],
                "options": {"receipt": "nao", "own_hand": "talvez", "reverse": "2"},
            }
        )


def test_insert_cart_payload_accepts_order_id_camel_case() -> None:
    oid = UUID("550e8400-e29b-41d4-a716-446655440000")
    req = InsertCartPayload.model_validate(
        {
            "service": 1,
            "from": {"name": "A", "address": "x", "number": "1", "district": "d", "city": "c", "postal_code": "123", "state_abbr": "SP"},
            "to": {"name": "B", "address": "y", "number": "2", "district": "d", "city": "c", "postal_code": "456", "state_abbr": "RJ"},
            "products": [{"name": "P", "quantity": "1", "unitary_value": "10"}],
            "orderId": str(oid),
        }
    )
    assert req.order_id == oid


def test_insert_cart_payload_to_phone_accepts_pascal_case_key() -> None:
    req = InsertCartPayload.model_validate(
        {
            "service": 1,
            "from": {"name": "A", "address": "x", "number": "1", "district": "d", "city": "c", "postal_code": "123", "state_abbr": "SP"},
            "to": {
                "name": "B",
                "address": "y",
                "number": "2",
                "district": "d",
                "city": "c",
                "postal_code": "456",
                "state_abbr": "RJ",
                "Phone": "11956758638",
            },
            "products": [{"name": "P", "quantity": "1", "unitary_value": "10"}],
        }
    )
    body = req.model_dump(by_alias=True, exclude_none=False, exclude={"order_id", "mp_payment_id", "payment_id"})
    assert body["to"]["phone"] == "11956758638"
