"""Schemas for Melhor Envio cart (inserir fretes no carrinho)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AddressBlock(BaseModel):
    """Remetente (from) ou destinatário (to). PF: document (CPF). PJ: company_document (CNPJ)."""

    model_config = ConfigDict(extra="allow")

    name: str
    address: str
    number: str
    district: str
    city: str
    country_id: str = "BR"
    postal_code: str
    state_abbr: str
    document: str | None = None
    company_document: str | None = None
    state_register: str | None = None
    email: str | None = None
    phone: str | None = None
    complement: str | None = None
    note: str | None = None
    economic_activity_code: str | None = None


class ProductItem(BaseModel):
    """Item da declaração de conteúdo."""

    model_config = ConfigDict(extra="allow")

    name: str
    quantity: str
    unitary_value: str


class VolumeItem(BaseModel):
    """Dimensões e peso de um volume (pacote)."""

    height: int | float
    width: int | float
    length: int | float
    weight: int | float


class InvoiceOption(BaseModel):
    """Chave da NF-e (envio comercial)."""

    key: str


class CartOptions(BaseModel):
    """Opções do envio (seguro, AR, mãos próprias, etc.)."""

    model_config = ConfigDict(extra="allow")

    insurance_value: float | None = None
    receipt: bool | None = None
    own_hand: bool | None = None
    reverse: bool | None = None
    non_commercial: bool | None = None
    invoice: InvoiceOption | None = None
    platform: str | None = None
    reminder: str | None = None
    tags: list[dict[str, str]] | None = None


class InsertCartPayload(BaseModel):
    """Corpo da requisição POST /api/v2/me/cart conforme documentação Melhor Envio."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    service: int = Field(..., description="Id do serviço da transportadora")
    agency: int | None = Field(default=None, description="Id da agência (obrigatório para Latam, Azul, Buslog em alguns cenários)")
    from_: AddressBlock | dict[str, Any] = Field(..., alias="from", description="Remetente")
    to: AddressBlock | dict[str, Any] = Field(..., description="Destinatário")
    products: list[ProductItem] | list[dict[str, Any]] = Field(..., description="Produtos na declaração de conteúdo")
    volumes: list[VolumeItem] | list[dict[str, Any]] = Field(..., description="Volumes (dimensões e peso)")
    options: CartOptions | dict[str, Any] | None = Field(default=None, description="Seguro, AR, NF, etc.")
