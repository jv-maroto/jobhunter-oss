"""Cliente MCP minimal para descubrir ofertas via stdio (lazy, OFF por defecto).

Requiere el extra `mcp` y un servidor MCP instalado (p.ej. linkedin-mcp-server).
Si esta deshabilitado o el SDK no esta, devuelve [] sin romper nada.
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.apply.base import JobLead
from app.mcp.registry import MCPServerSpec, linkedin_spec

logger = logging.getLogger(__name__)


def _parse_leads(tool_result: object, source: str) -> list[JobLead]:
    """Normaliza la salida del tool MCP (lista de dicts) a JobLead."""
    items: list = []
    # El SDK devuelve content con .text (json) en la mayoria de servidores.
    content = getattr(tool_result, "content", None)
    if content:
        for block in content:
            text = getattr(block, "text", None)
            if not text:
                continue
            try:
                data = json.loads(text)
                items = data if isinstance(data, list) else data.get("jobs", [])
            except Exception:  # noqa: BLE001
                continue
    leads: list[JobLead] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        leads.append(
            JobLead(
                title=str(it.get("title") or it.get("job_title") or ""),
                company=str(it.get("company") or it.get("company_name") or ""),
                url=str(it.get("url") or it.get("job_url") or it.get("link") or ""),
                location=str(it.get("location") or ""),
                description=str(it.get("description") or "")[:8000],
                source=source,
            )
        )
    return [le for le in leads if le.title and le.company]


async def _discover_async(spec: MCPServerSpec, query: str, location: str | None, limit: int) -> list[JobLead]:
    from mcp import ClientSession, StdioServerParameters  # type: ignore[import-not-found]
    from mcp.client.stdio import stdio_client  # type: ignore[import-not-found]

    params = StdioServerParameters(command=spec.command, args=spec.args, env=spec.env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            args = {"keywords": query, "limit": limit}
            if location:
                args["location"] = location
            result = await session.call_tool("search_jobs", args)
            return _parse_leads(result, source=f"{spec.name}-mcp")


def discover_linkedin_jobs(query: str, location: str | None = None, limit: int = 10) -> list[JobLead]:
    """Descubre ofertas via linkedin-mcp. [] si esta deshabilitado o falla."""
    spec = linkedin_spec()
    if spec is None:
        return []
    try:
        return asyncio.run(_discover_async(spec, query, location, limit))
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP discover fallo (¿SDK 'mcp' instalado? ¿servidor disponible?): %s", exc)
        return []
