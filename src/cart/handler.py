"""AWS Lambda handler for Melhor Envio cart endpoints."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any
from urllib.parse import quote

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from cart_repository import CartRepository
from cart_schemas import InsertCartPayload
from cart_service import CartService
from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import load_config
from shared.melhor_envio_oauth import MelhorEnvioOAuthClient
from shared.supabase import SupabaseConfig, SupabaseRestClient
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


def _extract_store_order_id(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Extrai order_id interno da loja para persistência local (não envia ao Melhor Envio)."""
    normalized = dict(payload)
    raw_id = normalized.pop("order_id", None) or normalized.pop("store_order_id", None)
    if raw_id is None:
        return None, normalized
    order_id = str(raw_id).strip()
    return (order_id or None), normalized


def _sync_order_with_cart_item(*, http: HttpClient, order_id: str, cart_item_id: Any) -> None:
    """Persiste o id do pedido no Melhor Envio para posterior tracking/notificação."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY env vars.")

    sb_cfg = SupabaseConfig(url=supabase_url, service_role_key=supabase_key)
    sb = SupabaseRestClient(http=http, cfg=sb_cfg)
    safe_order_id = quote(order_id, safe="")
    sb.patch(
        "orders",
        query=f"?id=eq.{safe_order_id}",
        json_body={
            "melhor_envio_order_id": str(cart_item_id),
            "updated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        },
    )


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
        payload_dict = payload if isinstance(payload, dict) else {}
        order_id, payload_for_melhor_envio = _extract_store_order_id(payload_dict)
        req = InsertCartPayload.model_validate(payload_for_melhor_envio)
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

        # Corpo no formato da API: "from" (não from_) via model_dump(by_alias=True)
        body_for_api = req.model_dump(by_alias=True, exclude_none=False)
        svc = _build_service()
        status, api_body = svc.insert_freights(authorization=authorization, payload=body_for_api)

        cart_item_id = api_body.get("id") if isinstance(api_body, dict) else None
        protocol = api_body.get("protocol") if isinstance(api_body, dict) else None
        if order_id and cart_item_id:
            try:
                _sync_order_with_cart_item(http=http, order_id=order_id, cart_item_id=cart_item_id)
            except Exception:
                metrics.add_metric(name="CartOrderSyncError", unit=MetricUnit.Count, value=1)
                logger.exception("Failed to sync cart item id with orders table", extra={"order_id": order_id})
        response_body = {
            "success": True,
            "cart_item_id": cart_item_id,
            "protocol": protocol,
            "status": api_body.get("status") if isinstance(api_body, dict) else None,
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
        return Response(
            status_code=502,
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

