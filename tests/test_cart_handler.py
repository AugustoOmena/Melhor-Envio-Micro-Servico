from __future__ import annotations

from pydantic import BaseModel

from handler import _inject_order_phone_into_destination


class _FakeTo(BaseModel):
    name: str
    city: str = "X"
    phone: str | None = None


def test_inject_order_phone_when_to_phone_missing() -> None:
    payload = {"to": {"name": "Destinatario"}, "service": 1}
    out = _inject_order_phone_into_destination(body_for_api=payload, payer_phone="24981021079")
    assert out["to"]["phone"] == "24981021079"


def test_does_not_override_existing_to_phone() -> None:
    payload = {"to": {"name": "Destinatario", "phone": "11999998888"}, "service": 1}
    out = _inject_order_phone_into_destination(body_for_api=payload, payer_phone="24981021079")
    assert out["to"]["phone"] == "11999998888"


def test_inject_order_phone_when_to_is_pydantic_model() -> None:
    payload = {"to": _FakeTo(name="Destinatario", phone=None), "service": 1}
    out = _inject_order_phone_into_destination(body_for_api=payload, payer_phone="24981021079")
    assert isinstance(out["to"], dict)
    assert out["to"]["phone"] == "24981021079"
    assert out["to"]["name"] == "Destinatario"
