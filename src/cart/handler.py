"""AWS Lambda handler for Melhor Envio cart endpoints."""

from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from cart_repository import CartRepository
from cart_schemas import InsertCartRequest
from cart_service import CartService
from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import load_config

logger = Logger(service="melhorenvio-cart")
tracer = Tracer(service="melhorenvio-cart")
metrics = Metrics(namespace="MelhorEnvioMicroservice", service="melhorenvio-cart")

app = APIGatewayHttpResolver()


def _build_service() -> CartService:
    cfg = load_config()
    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    repo = CartRepository(http=http, config=cfg)
    return CartService(repo=repo)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/cart")
@tracer.capture_method
def insert_cart() -> Response:
    auth = app.current_event.headers.get("authorization") if app.current_event.headers else None
    if not auth:
        metrics.add_metric(name="CartMissingAuth", unit=MetricUnit.Count, value=1)
        return Response(status_code=401, content_type="application/json", body={"message": "missing_authorization"})

    try:
        payload = app.current_event.json_body
        req = InsertCartRequest.model_validate(payload)
    except ValidationError as e:
        metrics.add_metric(name="CartValidationError", unit=MetricUnit.Count, value=1)
        return Response(status_code=400, content_type="application/json", body={"message": "invalid_request", "errors": e.errors()})

    try:
        svc = _build_service()
        status, body = svc.insert_freights(authorization=auth, payload=req.root)
        metrics.add_metric(name="CartInsertSuccess", unit=MetricUnit.Count, value=1)
        return Response(status_code=status, content_type="application/json", body=body)
    except HttpClientError as e:
        metrics.add_metric(name="CartUpstreamError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Upstream cart error",
            extra={"status_code": e.status_code, "response_body": e.response_body},
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


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)

