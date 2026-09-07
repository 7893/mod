"""
Authentication & Authorization mechanisms for MOD API (KI-041).

Contracts:
1. Validates internal API key and signed short-lived action tokens.
2. Protects high-risk external calling endpoints (e.g. /api/insights/generate).
3. Provides standard FastAPI security dependencies so OpenAPI specs correctly reflect securitySchemes.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

api_key_header = APIKeyHeader(name="X-MOD-Auth-Token", auto_error=False)
action_token_header = APIKeyHeader(name="X-Action-Token", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

# Secret used to sign short-lived action tokens for authorized web sessions
_ACTION_SECRET = (
    os.getenv("MOD_INTERNAL_API_KEY")
    or os.getenv("MOD_SECRET_KEY")
    or "mod-internal-secret-salt-2026"
)


def get_current_action_token(time_offset: int = 0) -> str:
    """Generate a HMAC-SHA256 action token valid for the current hour window."""
    epoch_hour = int((time.time() + time_offset) // 3600)
    msg = f"mod:action:{epoch_hour}".encode("utf-8")
    return hmac.new(_ACTION_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def verify_action_token(token: str) -> bool:
    """Validate token against current and previous hour windows (grace period)."""
    if not token or len(token) < 16:
        return False
    for offset in (0, -3600):
        expected = get_current_action_token(time_offset=offset)
        if hmac.compare_digest(token, expected):
            return True
    return False


def verify_internal_auth(
    api_key: Optional[str] = Security(api_key_header),  # secret-scan: allow
    action_token: Optional[str] = Security(action_token_header),  # secret-scan: allow
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
) -> bool:
    """
    Verify caller authorization for protected endpoints.
    Accepts:
    - X-MOD-Auth-Token header matching MOD_INTERNAL_API_KEY or valid action_token
    - Authorization: Bearer <token> matching MOD_INTERNAL_API_KEY or valid action_token
    - X-Action-Token header matching valid action_token
    """
    configured_key = os.getenv("MOD_INTERNAL_API_KEY", "").strip()

    # 1. Check Bearer token
    if bearer and bearer.credentials:
        token = bearer.credentials.strip()
        if (configured_key and hmac.compare_digest(token, configured_key)) or verify_action_token(token):
            return True

    # 2. Check X-MOD-Auth-Token
    if api_key:
        token = api_key.strip()
        if (configured_key and hmac.compare_digest(token, configured_key)) or verify_action_token(token):
            return True

    # 3. Check X-Action-Token
    if action_token:
        token = action_token.strip()
        if verify_action_token(token):
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未授权访问：高危外部调用接口需要有效的内部访问凭据 (X-MOD-Auth-Token / Bearer / X-Action-Token)",
        headers={"WWW-Authenticate": "Bearer"},
    )
