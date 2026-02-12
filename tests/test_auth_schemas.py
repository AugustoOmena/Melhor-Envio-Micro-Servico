from __future__ import annotations

import pytest

from auth_schemas import TokenRequest


def test_token_request_authorization_code_requires_fields() -> None:
    with pytest.raises(ValueError):
        TokenRequest.model_validate({"grant_type": "authorization_code"})


def test_token_request_refresh_token_requires_field() -> None:
    with pytest.raises(ValueError):
        TokenRequest.model_validate({"grant_type": "refresh_token"})


def test_token_request_client_credentials_ok() -> None:
    req = TokenRequest.model_validate({"grant_type": "client_credentials"})
    assert req.grant_type == "client_credentials"

