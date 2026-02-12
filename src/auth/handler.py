"""AWS Lambda handler for Melhor Envio auth endpoints."""

from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.metrics import MetricUnit
from pydantic import ValidationError

from auth_repository import AuthRepository
from auth_schemas import TokenRequest
from auth_service import AuthService
from shared.http import HttpClient, HttpClientError
from shared.melhor_envio import load_config

logger = Logger(service="melhorenvio-auth")
tracer = Tracer(service="melhorenvio-auth")
metrics = Metrics(namespace="MelhorEnvioMicroservice", service="melhorenvio-auth")

app = APIGatewayHttpResolver()


def _build_service() -> AuthService:
    cfg = load_config()
    if not cfg.client_id or not cfg.client_secret:
        raise RuntimeError("Missing MELHOR_ENVIO_CLIENT_ID or MELHOR_ENVIO_CLIENT_SECRET env vars.")
    http = HttpClient(timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
    repo = AuthRepository(http=http, config=cfg)
    return AuthService(repo=repo, client_id=cfg.client_id, client_secret=cfg.client_secret)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/token")
@tracer.capture_method
def create_token() -> Response:
    try:
        payload = app.current_event.json_body or {}
        req = TokenRequest.model_validate(payload)
    except ValidationError as e:
        metrics.add_metric(name="AuthTokenValidationError", unit=MetricUnit.Count, value=1)
        return Response(status_code=400, content_type="application/json", body={"message": "invalid_request", "errors": e.errors()})

    try:
        svc = _build_service()
        token = svc.create_token(req)
        metrics.add_metric(name="AuthTokenSuccess", unit=MetricUnit.Count, value=1)
        return Response(status_code=200, content_type="application/json", body=token)
    except HttpClientError as e:
        metrics.add_metric(name="AuthTokenUpstreamError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Upstream token error",
            extra={"status_code": e.status_code, "response_body": e.response_body},
        )
        return Response(
            status_code=502,
            content_type="application/json",
            body={"message": "upstream_error", "status_code": e.status_code, "details": e.response_body},
        )
    except Exception:
        metrics.add_metric(name="AuthTokenUnhandledError", unit=MetricUnit.Count, value=1)
        logger.exception("Unhandled error creating token")
        return Response(status_code=500, content_type="application/json", body={"message": "internal_error"})


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return app.resolve(event, context)

