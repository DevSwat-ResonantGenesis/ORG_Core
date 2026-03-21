"""Authentication context for shared tools.

Provides a unified auth mechanism so that tools called from either
chat_service or agent_engine_service carry proper identity headers.

Platform auth architecture
--------------------------
* Browser → Gateway: ``rg_access_token`` HttpOnly cookie (or ``Authorization:
  Bearer <same-token>``, or ``RG-`` API key).
* Gateway validates token via ``auth_service POST /auth/verify``, then **strips
  the token** and injects identity headers (``x-user-id``, ``x-user-role``,
  ``x-org-id``, ``x-is-superuser``, ``x-unlimited-credits``, etc.).
* **Internal service-to-service calls never carry JWTs.**  They rely on the
  ``x-user-*`` headers already injected by the gateway.

Therefore, ``build_service_headers`` only emits ``x-user-*`` headers — it does
**not** forward a JWT Bearer token, because downstream services don't validate
JWTs; they trust the gateway-injected headers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AuthContext:
    """Authentication context passed to every shared tool.

    Populated by the caller (chat_service or agent_engine) from the
    gateway-injected ``x-user-*`` headers on the incoming request.
    """
    user_id: str = "anonymous"
    org_id: Optional[str] = None
    user_role: str = "user"
    user_plan: str = "free"
    is_superuser: bool = False
    unlimited_credits: bool = False
    github_token: Optional[str] = None       # For code_visualizer scans
    extra_headers: Dict[str, str] = field(default_factory=dict)

    # Internal service-to-service secret (set from env)
    _internal_secret: Optional[str] = field(
        default=None, repr=False,
    )

    def __post_init__(self):
        if self._internal_secret is None:
            self._internal_secret = os.getenv("INTERNAL_SERVICE_SECRET", "")


def build_service_headers(ctx: AuthContext) -> Dict[str, str]:
    """Build HTTP headers for internal service-to-service calls.

    Emits the same ``x-user-*`` headers that the gateway injects after
    validating the user's ``rg_access_token`` cookie.  Downstream services
    trust these headers — no JWT is forwarded.
    """
    headers: Dict[str, str] = {
        "x-user-id": ctx.user_id,
        "x-user-role": ctx.user_role,
        "x-is-superuser": "true" if ctx.is_superuser else "false",
    }

    if ctx.org_id:
        headers["x-org-id"] = ctx.org_id

    # Internal service secret for service-to-service trust
    if ctx._internal_secret:
        headers["x-internal-secret"] = ctx._internal_secret

    if ctx.unlimited_credits:
        headers["x-unlimited-credits"] = "true"

    if ctx.github_token:
        headers["x-github-token"] = ctx.github_token

    # Merge any extra headers from caller
    headers.update(ctx.extra_headers)

    return headers
