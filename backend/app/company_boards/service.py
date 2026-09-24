"""Refresh snapshots atomically; failures retain the last successful inventory."""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.company_boards.readers import fetch_board
from app.db import SessionLocal
from app.models.company_board import CompanyBoard


def stamp():
    return datetime.now(timezone.utc).isoformat()


def recover_interrupted_refreshes():
    with SessionLocal() as db:
        for row in db.scalars(select(CompanyBoard)):
            if row.last_refresh and row.last_refresh.get("status") == "running":
                row.last_refresh = {**row.last_refresh, "status": "interrupted", "finished_at": stamp(),
                                    "error": "Backend restarted; previous staged results retained"}
        db.commit()


async def refresh_board(board_id: int):
    with SessionLocal() as db:
        row = db.get(CompanyBoard, board_id)
        if row is None or not row.last_refresh or row.last_refresh.get("status") != "running":
            return
        run = dict(row.last_refresh)
        try:
            result = await fetch_board(row.provider, row.slug, row.name)
            row.staged_jobs = result.pop("jobs")
            row.last_refresh = {**run, **result, "status": "finished", "finished_at": stamp(), "staged": len(row.staged_jobs)}
        except asyncio.CancelledError:
            row.last_refresh = {**run, "status": "interrupted", "finished_at": stamp(), "error": "Refresh interrupted; previous staged results retained"}
            db.commit()
            raise
        except Exception as exc:
            logging.getLogger(__name__).warning("Board %s refresh failed (%s)", board_id, type(exc).__name__)
            error = (f"Provider returned HTTP {exc.response.status_code}; verify the board slug and retry later"
                     if isinstance(exc, httpx.HTTPStatusError) else "Could not read the board safely; previous staged results retained")
            row.last_refresh = {**run, "status": "failed", "finished_at": stamp(), "error": error}
        db.commit()
