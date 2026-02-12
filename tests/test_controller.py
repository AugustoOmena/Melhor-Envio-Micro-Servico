from __future__ import annotations

from unittest.mock import Mock

import pytest

from controller import BadRequestError, build_authorize_url, insert_cart, refresh_token, request_token
from service import MelhorEnvioService


def test_build_authorize_url_validates_body() -> None:
    svc = Mock(spec=MelhorEnvioService)

    with pytest.raises(BadRequestError):
        build_authorize_url(service=svc, body={})


def test_request_token_validates_body() -> None:
    svc = Mock(spec=MelhorEnvioService)

    with pytest.raises(BadRequestError):
        request_token(service=svc, body={"grant_type": "authorization_code"})


def test_refresh_token_validates_body() -> None:
    svc = Mock(spec=MelhorEnvioService)

    with pytest.raises(BadRequestError):
        refresh_token(service=svc, body={})


def test_insert_cart_requires_non_empty_object() -> None:
    svc = Mock(spec=MelhorEnvioService)

    with pytest.raises(BadRequestError):
        insert_cart(service=svc, access_token="x", body={})

