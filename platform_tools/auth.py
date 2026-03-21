"""Auth context shared across platform tools."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuthContext:
    """Authentication context passed from agent sessions to platform tools."""
    user_id: str = "agent-system"
    org_id: Optional[str] = None
    user_role: str = "user"
    is_superuser: bool = False
    unlimited_credits: bool = False

    def headers(self) -> dict:
        """Return headers suitable for internal service-to-service calls."""
        h = {"x-user-id": self.user_id}
        if self.org_id:
            h["x-org-id"] = self.org_id
        if self.user_role:
            h["x-user-role"] = self.user_role
        if self.is_superuser:
            h["x-is-superuser"] = "true"
        if self.unlimited_credits:
            h["x-unlimited-credits"] = "true"
        return h
