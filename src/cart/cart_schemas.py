"""Schemas (DTOs) for cart operations."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, RootModel


class InsertCartRequest(RootModel[Any]):
    """Pass-through JSON payload for Melhor Envio `/api/v2/me/cart`.

    The public docs render the schema dynamically; to avoid drift, we validate only that the payload is valid JSON.
    """

    model_config = ConfigDict(extra="allow")

