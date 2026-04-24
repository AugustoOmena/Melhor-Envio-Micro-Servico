"""AWS Lambda handler for Melhor Envio cart endpoints."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from cart_repository import CartRepository
from cart_schemas import InsertCartPayload
from cart_service import CartService
from orders_repository import OrdersRepository, PayerPhoneLookup
from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import load_config
from shared.melhor_envio_oauth import MelhorEnvioOAuthClient
from shared.supabase import SupabaseConfig, SupabaseError, SupabaseRestClient
from shared.token_store import MelhorEnvioTokenStore, TokenStoreError

logger = Logger(service="melhorenvio-cart")
tracer = Tracer(service="melhorenvio-cart")
metrics = Metrics(namespace="MelhorEnvioMicroservice", service="melhorenvio-cart")

app = APIGatewayHttpResolver()

ADMIN_SUBJECT = "admin"

def _build_service() -> CartService:
    cfg = load_config()
    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    user_agent = os.getenv("MELHOR_ENVIO_USER_AGENT", "MelhorEnvio-Integration (contato@example.com)")
    repo = CartRepository(http=http, config=cfg, user_agent=user_agent)
    return CartService(repo=repo)

def _build_token_store(http: HttpClient) -> MelhorEnvioTokenStore:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY env vars.")

    sb_cfg = SupabaseConfig(url=supabase_url, service_role_key=supabase_key)
    sb = SupabaseRestClient(http=http, cfg=sb_cfg)
    return MelhorEnvioTokenStore(sb)

def _build_orders_repo(http: HttpClient) -> OrdersRepository:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY env vars.")
    sb_cfg = SupabaseConfig(url=supabase_url, service_role_key=supabase_key)
    sb = SupabaseRestClient(http=http, cfg=sb_cfg)
    return OrdersRepository(sb)


def _address_block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return dict(block)
    model_dump = getattr(block, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(by_alias=True, exclude_none=False)
        if isinstance(dumped, dict):
            return dict(dumped)
    return {}


def _extract_melhor_envio_cart_id(api_body: Any) -> Any:
    if isinstance(api_body, dict):
        rid = api_body.get("id")
        if rid is not None:
            return rid
        data = api_body.get("data")
        if isinstance(data, dict) and data.get("id") is not None:
            return data.get("id")
        if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id") is not None:
            return data[0].get("id")
    if isinstance(api_body, list) and api_body:
        first = api_body[0]
        if isinstance(first, dict) and first.get("id") is not None:
            return first.get("id")
    return None


def _inject_order_phone_into_destination(*, body_for_api: dict[str, Any], payer_phone: str | None) -> dict[str, Any]:
    if not payer_phone:
        return body_for_api
    to_block = _address_block_to_dict(body_for_api.get("to"))
    if not to_block:
        return body_for_api
    current_phone = to_block.get("phone")
    if current_phone is not None and str(current_phone).strip():
        return body_for_api
    return {**body_for_api, "to": {**to_block, "phone": payer_phone}}


_PAC_PHONE_HINTS: dict[str, str] = {
    "no_order_id": "Inclua to.phone no destinatário ou order_id / orderId do pedido (telefone vem de orders.payer.phone).",
    "no_order_row": "Não encontramos pedido com order_id (orders.id), mp_payment_id ou payment_id. Confira os valores e o projeto Supabase da Lambda (sql/01_init_schema.sql).",
    "payer_column_null": "Pedido encontrado, mas orders.payer está vazio. Preencha payer com phone ou envie to.phone.",
    "payer_not_json_object": "orders.payer não é um objeto JSON. Corrija o registo ou envie to.phone.",
    "payer_dict_without_phone": "orders.payer não tem phone. Atualize payer.phone ou envie to.phone.",
    "payer_phone_blank": "orders.payer.phone está vazio. Corrija ou envie to.phone.",
}


def _pac_phone_denial_reason(*, payer_lookup: PayerPhoneLookup | None) -> str:
    if payer_lookup is None:
        return "no_order_id"
    return payer_lookup.payer_state


def _pac_phone_denial_hint(reason: str) -> str:
    tail = _PAC_PHONE_HINTS.get(reason, "Envie to.phone no destinatário ou corrija order_id / orders.payer.")
    return f"PAC (serviço 3) exige telefone no destinatário. {tail}"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _handle_cart() -> Response:
    """
    Adiciona etiquetas ao carrinho do Melhor Envio.
    Recupera token do Supabase, renova se próximo do vencimento, envia POST /api/v2/me/cart.
    """
    try:
        payload = app.current_event.json_body
        req = InsertCartPayload.model_validate(payload)
    except ValidationError as e:
        metrics.add_metric(name="CartValidationError", unit=MetricUnit.Count, value=1)
        return Response(status_code=400, content_type="application/json", body={"message": "invalid_request", "errors": e.errors()})

    try:
        cfg = load_config()
        http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))

        auth_header = app.current_event.headers.get("authorization") if app.current_event.headers else None
        used_stored_token = not bool(auth_header)

        if auth_header:
            authorization = auth_header
        else:
            store = _build_token_store(http)
            rec = store.get(subject=ADMIN_SUBJECT, env=cfg.env)
            if rec is None:
                metrics.add_metric(name="CartNotConnected", unit=MetricUnit.Count, value=1)
                return Response(
                    status_code=409,
                    content_type="application/json",
                    body={"message": "melhor_envio_not_connected", "hint": "Conecte o Melhor Envio no backoffice."},
                )

            now = dt.datetime.now(tz=dt.timezone.utc)
            if rec.expires_at and rec.expires_at <= (now + dt.timedelta(minutes=5)) and rec.refresh_token:
                if not cfg.client_id or not cfg.client_secret:
                    return Response(
                        status_code=500,
                        content_type="application/json",
                        body={"message": "missing_credentials", "hint": "Configure client_id e client_secret."},
                    )
                try:
                    oauth = MelhorEnvioOAuthClient(http=http, config=cfg)
                    refreshed = oauth.request_token(
                        {
                            "grant_type": "refresh_token",
                            "client_id": cfg.client_id,
                            "client_secret": cfg.client_secret,
                            "refresh_token": rec.refresh_token,
                        }
                    )
                    rec = store.upsert_from_token_response(subject=ADMIN_SUBJECT, env=cfg.env, token_response=refreshed)
                except HttpClientError as refresh_err:
                    metrics.add_metric(name="CartRefreshFailed", unit=MetricUnit.Count, value=1)
                    try:
                        store.delete(subject=ADMIN_SUBJECT, env=cfg.env)
                    except Exception:
                        pass
                    return Response(
                        status_code=401,
                        content_type="application/json",
                        body={
                            "message": "token_expired",
                            "hint": "Reconecte o Melhor Envio no backoffice.",
                            "details": refresh_err.response_body,
                        },
                    )

            authorization = f"{rec.token_type} {rec.access_token}"

        # Corpo no formato da API: "from" (não from_) via model_dump(by_alias=True); campos de pedido não vão ao ME.
        body_for_api = req.model_dump(
            by_alias=True,
            exclude_none=False,
            exclude={"order_id", "mp_payment_id", "payment_id"},
        )
        to_before_phone = _address_block_to_dict(body_for_api.get("to")).get("phone")
        had_to_phone = bool(to_before_phone is not None and str(to_before_phone).strip())

        orders_repo: OrdersRepository | None = None
        payer_phone: str | None = None
        payer_lookup: PayerPhoneLookup | None = None
        mp_pay = (req.mp_payment_id or "").strip() or None
        pay_id = (req.payment_id or "").strip() or None
        if req.order_id is not None or mp_pay is not None or pay_id is not None:
            try:
                orders_repo = _build_orders_repo(http)
            except RuntimeError:
                metrics.add_metric(name="CartOrderPersistConfigError", unit=MetricUnit.Count, value=1)
                return Response(
                    status_code=500,
                    content_type="application/json",
                    body={
                        "message": "missing_supabase_config",
                        "hint": "SUPABASE_URL e SUPABASE_KEY são necessários para order_id, mp_payment_id ou payment_id.",
                    },
                )
            if req.order_id is not None:
                payer_lookup = orders_repo.lookup_payer_phone(order_id=req.order_id)
            elif mp_pay is not None:
                payer_lookup = orders_repo.lookup_payer_phone(mp_payment_id=mp_pay)
            else:
                payer_lookup = orders_repo.lookup_payer_phone(payment_id=pay_id)
            payer_phone = payer_lookup.phone if payer_lookup else None
            body_for_api = _inject_order_phone_into_destination(body_for_api=body_for_api, payer_phone=payer_phone)

        if body_for_api.get("service") == 3:
            to_phone = _address_block_to_dict(body_for_api.get("to")).get("phone")
            if not (to_phone and str(to_phone).strip()):
                metrics.add_metric(name="CartMissingDestinationPhone", unit=MetricUnit.Count, value=1)
                reason = _pac_phone_denial_reason(payer_lookup=payer_lookup)
                logger.warning(
                    "cart_pac_destination_phone_missing",
                    extra={
                        "reason": reason,
                        "order_id": str(req.order_id) if req.order_id else None,
                        "used_mp_payment_id": bool(mp_pay),
                        "used_payment_id": bool(pay_id),
                        "had_to_phone_before_inject": had_to_phone,
                        "payer_phone_loaded": payer_phone is not None,
                    },
                )
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body={
                        "message": "destination_phone_required",
                        "reason": reason,
                        "hint": _pac_phone_denial_hint(reason),
                    },
                )

        to_after = _address_block_to_dict(body_for_api.get("to"))
        after_phone = to_after.get("phone")
        payer_phone_injected = bool(
            payer_phone
            and (not had_to_phone)
            and after_phone is not None
            and str(after_phone).strip() == payer_phone.strip()
        )

        svc = _build_service()
        status, api_body = svc.insert_freights(authorization=authorization, payload=body_for_api)

        cart_item_id = _extract_melhor_envio_cart_id(api_body)
        protocol = api_body.get("protocol") if isinstance(api_body, dict) else None
        if protocol is None and isinstance(api_body, list) and api_body and isinstance(api_body[0], dict):
            protocol = api_body[0].get("protocol")
        melhor_envio_order_id = str(cart_item_id) if cart_item_id is not None else None

        order_updated: bool | None = None
        persist_order_id = req.order_id
        if payer_lookup is not None and payer_lookup.resolved_order_id is not None:
            persist_order_id = payer_lookup.resolved_order_id
        if persist_order_id is not None and melhor_envio_order_id is not None:
            try:
                if orders_repo is None:
                    orders_repo = _build_orders_repo(http)
                order_updated = orders_repo.set_melhor_envio_order_id(
                    order_id=persist_order_id,
                    melhor_envio_order_id=melhor_envio_order_id,
                )
                if not order_updated:
                    logger.warning(
                        "Nenhuma linha em orders atualizada",
                        extra={"order_id": str(persist_order_id), "melhor_envio_order_id": melhor_envio_order_id},
                    )
            except SupabaseError as e:
                metrics.add_metric(name="CartOrderPersistError", unit=MetricUnit.Count, value=1)
                logger.exception("Falha ao gravar melhor_envio_order_id em orders", extra={"error": str(e)})
                return Response(
                    status_code=502,
                    content_type="application/json",
                    body={
                        "message": "order_persist_failed",
                        "hint": "Carrinho no Melhor Envio foi atualizado; corrija a persistência ou reconcilie manualmente.",
                        "details": str(e),
                        "cart_item_id": cart_item_id,
                        "melhor_envio_order_id": melhor_envio_order_id,
                    },
                )

        response_status = api_body.get("status") if isinstance(api_body, dict) else None
        if response_status is None and isinstance(api_body, list) and api_body and isinstance(api_body[0], dict):
            response_status = api_body[0].get("status")
        response_body = {
            "success": True,
            "cart_item_id": cart_item_id,
            "melhor_envio_order_id": melhor_envio_order_id,
            "protocol": protocol,
            "status": response_status,
            "order_updated": order_updated,
            "payer_phone_injected": payer_phone_injected,
            "data": api_body,
        }
        metrics.add_metric(name="CartInsertSuccess", unit=MetricUnit.Count, value=1)
        return Response(status_code=status, content_type="application/json", body=response_body)
    except TokenStoreError as e:
        metrics.add_metric(name="CartTokenStoreError", unit=MetricUnit.Count, value=1)
        logger.warning("Token store error", extra={"error": str(e)})
        return Response(status_code=502, content_type="application/json", body={"message": "token_store_error"})
    except HttpClientError as e:
        metrics.add_metric(name="CartUpstreamError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Upstream cart error",
            extra={"status_code": e.status_code, "response_body": e.response_body},
        )
        if e.status_code == 401:
            if used_stored_token:
                try:
                    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
                    store = _build_token_store(http)
                    store.delete(subject=ADMIN_SUBJECT, env=load_config().env)
                except Exception:
                    pass
            return Response(
                status_code=401,
                content_type="application/json",
                body={
                    "message": "token_expired",
                    "hint": "Reconecte o Melhor Envio no backoffice.",
                    "details": e.response_body,
                },
            )
        out_status = e.status_code if e.status_code is not None and 400 <= e.status_code < 500 else 502
        return Response(
            status_code=out_status,
            content_type="application/json",
            body={"message": "upstream_error", "status_code": e.status_code, "details": e.response_body},
        )
    except Exception:
        metrics.add_metric(name="CartUnhandledError", unit=MetricUnit.Count, value=1)
        logger.exception("Unhandled error inserting cart")
        return Response(status_code=500, content_type="application/json", body={"message": "internal_error"})


@app.post("/cart")
@tracer.capture_method
def insert_cart() -> Response:
    return _handle_cart()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)

