"""
Tests for internal API authentication and token verification (KI-041).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import (
    get_current_action_token,
    verify_action_token,
    verify_internal_auth,
)
from fastapi.security import HTTPAuthorizationCredentials


def test_action_token_generation_and_verification():
    token = get_current_action_token()
    assert isinstance(token, str)
    assert len(token) >= 16

    # Valid token passes
    assert verify_action_token(token) is True

    # Modified or empty token fails
    assert verify_action_token("") is False
    assert verify_action_token("short") is False
    assert verify_action_token(token[:-4] + "xxxx") is False


def test_verify_internal_auth_with_configured_key(monkeypatch):
    monkeypatch.setenv("MOD_INTERNAL_API_KEY", "super-secret-key-12345")

    # 1. Matching api_key header
    assert verify_internal_auth(api_key="super-secret-key-12345", action_token=None, bearer=None) is True  # secret-scan: allow

    # 2. Matching Bearer token
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials="super-secret-key-12345")
    assert verify_internal_auth(api_key=None, action_token=None, bearer=bearer) is True

    # 3. Wrong key fails with 401
    with pytest.raises(HTTPException) as exc:
        verify_internal_auth(api_key="wrong-key", action_token=None, bearer=None)  # secret-scan: allow
    assert exc.value.status_code == 401

    # 4. Missing credentials fails with 401
    with pytest.raises(HTTPException) as exc:
        verify_internal_auth(api_key=None, action_token=None, bearer=None)
    assert exc.value.status_code == 401


def test_verify_internal_auth_with_action_token():
    valid_token = get_current_action_token()

    # Via action_token param
    assert verify_internal_auth(api_key=None, action_token=valid_token, bearer=None) is True  # secret-scan: allow

    # Via api_key param
    assert verify_internal_auth(api_key=valid_token, action_token=None, bearer=None) is True  # secret-scan: allow

    # Via Bearer credentials
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
    assert verify_internal_auth(api_key=None, action_token=None, bearer=bearer) is True
