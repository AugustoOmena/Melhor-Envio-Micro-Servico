from __future__ import annotations

from typing import Any

import pytest

from cart_service import CartService, _BOX_HEIGHT, _BOX_LENGTH, _BOX_WEIGHT, _BOX_WIDTH


class _FakeRepo:
    def __init__(self) -> None:
        self.last_auth: str | None = None
        self.last_payload: Any | None = None

    def insert_cart(self, *, authorization: str, payload: Any) -> tuple[int, Any]:
        self.last_auth = authorization
        self.last_payload = payload
        return 200, {"ok": True}


def _make_svc() -> tuple[CartService, _FakeRepo]:
    repo = _FakeRepo()
    return CartService(repo=repo), repo


def test_standard_box_replaces_volumes() -> None:
    svc, repo = _make_svc()
    payload = {
        "service": 1,
        "from": {"name": "A"},
        "to": {"name": "B"},
        "products": [{"name": "X", "quantity": "2", "unitary_value": "10"}],
        "volumes": [{"height": 99, "width": 99, "length": 99, "weight": 1.0}],
    }
    svc.insert_freights(authorization="Bearer t", payload=payload)

    vol = repo.last_payload["volumes"]
    assert len(vol) == 1
    assert vol[0]["height"] == _BOX_HEIGHT
    assert vol[0]["width"] == _BOX_WIDTH
    assert vol[0]["length"] == _BOX_LENGTH
    assert vol[0]["weight"] == _BOX_WEIGHT
    assert vol[0]["quantity"] == 2


def test_total_qty_sums_all_products() -> None:
    svc, repo = _make_svc()
    payload = {
        "service": 1,
        "from": {}, "to": {},
        "products": [
            {"quantity": "3"},
            {"quantity": "2"},
            {"quantity": "1"},
        ],
    }
    svc.insert_freights(authorization="Bearer t", payload=payload)
    assert repo.last_payload["volumes"][0]["quantity"] == 6


def test_missing_quantity_defaults_to_one_per_product() -> None:
    svc, repo = _make_svc()
    payload = {
        "service": 1,
        "from": {}, "to": {},
        "products": [{"name": "X"}, {"name": "Y"}],
    }
    svc.insert_freights(authorization="Bearer t", payload=payload)
    assert repo.last_payload["volumes"][0]["quantity"] == 2


def test_empty_products_quantity_defaults_to_one() -> None:
    svc, repo = _make_svc()
    payload = {"service": 1, "from": {}, "to": {}, "products": []}
    svc.insert_freights(authorization="Bearer t", payload=payload)
    assert repo.last_payload["volumes"][0]["quantity"] == 1


def test_insurance_value_set_to_one_when_absent() -> None:
    svc, repo = _make_svc()
    payload = {"service": 1, "from": {}, "to": {}, "products": [{"quantity": "1"}]}
    svc.insert_freights(authorization="Bearer t", payload=payload)
    assert repo.last_payload["options"]["insurance_value"] == 1


def test_insurance_value_preserved_when_already_set() -> None:
    svc, repo = _make_svc()
    payload = {
        "service": 1, "from": {}, "to": {},
        "products": [{"quantity": "1"}],
        "options": {"insurance_value": 50.0},
    }
    svc.insert_freights(authorization="Bearer t", payload=payload)
    assert repo.last_payload["options"]["insurance_value"] == 50.0


def test_authorization_forwarded() -> None:
    svc, repo = _make_svc()
    svc.insert_freights(authorization="Bearer xyz", payload={"products": []})
    assert repo.last_auth == "Bearer xyz"


def test_non_dict_payload_passed_through() -> None:
    svc, repo = _make_svc()
    svc.insert_freights(authorization="Bearer t", payload="raw_string")
    assert repo.last_payload == "raw_string"
