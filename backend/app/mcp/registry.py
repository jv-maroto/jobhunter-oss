"""Registro de servidores MCP configurados (desde .env). Todo OFF por defecto."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings


@dataclass
class MCPServerSpec:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = False


def linkedin_spec() -> MCPServerSpec | None:
    """Spec del linkedin-mcp-server si esta habilitado y hay cookie. Si no, None."""
    if not settings.mcp_linkedin_enabled or not settings.linkedin_cookie:
        return None
    parts = (settings.mcp_linkedin_args or "linkedin-mcp-server").split()
    if not parts:
        return None
    return MCPServerSpec(
        name="linkedin",
        command=parts[0],
        args=parts[1:],
        env={"LINKEDIN_COOKIE": settings.linkedin_cookie},
        enabled=True,
    )
