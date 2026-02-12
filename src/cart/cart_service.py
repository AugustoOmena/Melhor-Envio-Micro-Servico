"""Business logic for Melhor Envio cart operations."""

from __future__ import annotations

from typing import Any

from cart_repository import CartRepository


class CartService:
    def __init__(self, repo: CartRepository) -> None:
        self._repo = repo

    def insert_freights(self, *, authorization: str, payload: Any) -> tuple[int, Any]:
        return self._repo.insert_cart(authorization=authorization, payload=payload)

