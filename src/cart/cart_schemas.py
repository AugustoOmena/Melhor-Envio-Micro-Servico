"""Schemas for Melhor Envio cart (inserir fretes no carrinho).

Alinhado à API POST /api/v2/me/cart: dimensões em cm como inteiros; peso em kg
com precisão decimal controlada. O microserviço de carrinho apenas valida e
repassa o payload — sem recálculo de frete; a cotação deve enviar os mesmos
tipos/normalização para evitar divergência de valores.

Refs: https://docs.melhorenvio.com.br/reference/inserir-fretes-no-carrinho
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_serializer, field_validator


def _to_int_cm(value: Any) -> int:
    """Dimensões em cm: sempre inteiro, arredondamento para cima (evita subdimensionar)."""
    if isinstance(value, bool):
        raise ValueError("dimensão não pode ser boolean")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("dimensão não pode ser negativa")
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("dimensão inválida")
        if value < 0:
            raise ValueError("dimensão não pode ser negativa")
        return int(math.ceil(value))
    if isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError("dimensão vazia")
        try:
            d = Decimal(s)
        except InvalidOperation as e:
            raise ValueError("dimensão não numérica") from e
        if d < 0:
            raise ValueError("dimensão não pode ser negativa")
        return int(math.ceil(float(d)))
    raise ValueError("dimensão deve ser numérica (cm)")


def _to_weight_kg(value: Any) -> Decimal:
    """Peso em kg como Decimal; no máximo 3 casas decimais (quantize, sem alterar se já válido)."""
    if isinstance(value, bool):
        raise ValueError("peso não pode ser boolean")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("peso inválido")
        d = Decimal(str(value))
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError("peso vazio")
        try:
            d = Decimal(s)
        except InvalidOperation as e:
            raise ValueError("peso não numérico") from e
    else:
        raise ValueError("peso deve ser numérico (kg)")
    if d < 0:
        raise ValueError("peso não pode ser negativo")
    q = Decimal("0.001")
    quantized = d.quantize(q)
    # Rejeita mais de 3 casas decimais (evita float silencioso com 1.2345)
    if quantized != d:
        raise ValueError("peso em kg deve ter no máximo 3 casas decimais")
    return quantized


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
    phone: str | None = Field(default=None, validation_alias=AliasChoices("phone", "Phone"))
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
    """Dimensões (cm) e peso (kg) de um volume — espelha o que a cotação envia; só valida/normaliza tipos.

    OpenAPI Melhor Envio: height, width, length como integer; weight como number.
    quantity: número de caixas idênticas neste volume (padrão 1).
    """

    model_config = ConfigDict(extra="allow")

    height: int = Field(..., description="Altura em cm (inteiro, ceil se fracionário)")
    width: int = Field(..., description="Largura em cm (inteiro, ceil se fracionário)")
    length: int = Field(..., description="Comprimento em cm (inteiro, ceil se fracionário)")
    weight: Decimal = Field(..., description="Peso em kg (Decimal, máx. 3 casas decimais)")
    quantity: int = Field(default=1, ge=1, description="Quantidade de caixas idênticas")

    @field_validator("height", "width", "length", mode="before")
    @classmethod
    def _ceil_dimensions_cm(cls, v: Any) -> int:
        return _to_int_cm(v)

    @field_validator("weight", mode="before")
    @classmethod
    def _weight_max_three_decimals(cls, v: Any) -> Decimal:
        return _to_weight_kg(v)

    @field_serializer("weight", when_used="always")
    def _serialize_weight_for_json(self, v: Decimal) -> float:
        """json.dumps não serializa Decimal; API espera number (float com até 3 decimais estável)."""
        return float(v)


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
    """Corpo da requisição POST /api/v2/me/cart conforme documentação Melhor Envio.

    volumes: sempre lista de VolumeItem após validação (mesma forma que a cotação deve enviar).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    service: int = Field(..., description="Id do serviço da transportadora")
    agency: int | None = Field(default=None, description="Id da agência (obrigatório para Latam, Azul, Buslog em alguns cenários)")
    from_: AddressBlock = Field(..., alias="from", description="Remetente")
    to: AddressBlock = Field(..., description="Destinatário")
    products: list[ProductItem] = Field(..., description="Produtos na declaração de conteúdo")
    volumes: list[VolumeItem] | None = Field(default=None, description="Ignorado — o serviço sempre usa a caixa padrão calculada a partir dos products")
    options: CartOptions | None = Field(default=None, description="Seguro, AR, NF, etc.")
    order_id: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("order_id", "orderId"),
        description="Pedido interno (orders.id); se informado, persiste o id retornado pelo Melhor Envio em orders.melhor_envio_order_id",
    )
