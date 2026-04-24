"""Business logic for Melhor Envio cart operations."""

from __future__ import annotations

from typing import Any

from cart_repository import CartRepository

# Dimensões fixas da caixa padrão (alinhadas ao backend de pagamento).
# Uma unidade lógica = 1 caixa 16×12×20 cm, 0,3 kg.
# quantity = soma das quantidades de todos os itens do pedido.
_BOX_WIDTH = 16
_BOX_HEIGHT = 12
_BOX_LENGTH = 20
_BOX_WEIGHT = 0.3


def _compute_standard_volumes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Retorna um único volume com a caixa padrão; quantity = soma das qtds dos products."""
    products = payload.get("products") or []
    total_qty = 0
    for p in products:
        raw = p.get("quantity", 1) if isinstance(p, dict) else 1
        try:
            total_qty += int(raw)
        except (TypeError, ValueError):
            total_qty += 1
    return [{
        "height": _BOX_HEIGHT,
        "width": _BOX_WIDTH,
        "length": _BOX_LENGTH,
        "weight": _BOX_WEIGHT,
        "quantity": max(total_qty, 1),
    }]


def _ensure_minimum_insurance(payload: dict[str, Any]) -> dict[str, Any]:
    """Garante insurance_value=1 nas options se não foi informado."""
    options = payload.get("options") or {}
    if isinstance(options, dict) and options.get("insurance_value") is None:
        options = {**options, "insurance_value": 1}
    return {**payload, "options": options}


def _coerce_me_bool(value: Any) -> bool | Any:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes", "sim"):
            return True
        if s in ("false", "0", "no", "não", "nao"):
            return False
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return value


def _normalize_me_options(options: dict[str, Any], *, service: Any) -> dict[str, Any]:
    out = dict(options)
    for key in ("receipt", "own_hand", "reverse"):
        if key not in out:
            continue
        coerced = _coerce_me_bool(out[key])
        if isinstance(coerced, bool):
            out[key] = coerced
    if service == 3:
        for key in ("receipt", "own_hand", "reverse"):
            if key not in out or out[key] is None:
                out[key] = False
            elif out[key] is not None and not isinstance(out[key], bool):
                c = _coerce_me_bool(out[key])
                out[key] = c if isinstance(c, bool) else False
    return out


class CartService:
    def __init__(self, repo: CartRepository) -> None:
        self._repo = repo

    def insert_freights(self, *, authorization: str, payload: Any) -> tuple[int, Any]:
        normalized = self._normalize(payload)
        return self._repo.insert_cart(authorization=authorization, payload=normalized)

    def _normalize(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return payload
        result = dict(payload)
        result["volumes"] = _compute_standard_volumes(result)
        opts = result.get("options")
        if not isinstance(opts, dict):
            opts = {}
        result["options"] = _normalize_me_options(opts, service=result.get("service"))
        result = _ensure_minimum_insurance(result)
        return result
