"""Small persistent task journal; execution remains in the single local worker."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models.task_run import TaskRun


def begin_task(kind: str, state: dict) -> int:
    # Also supports maintenance commands that invoke services without app startup.
    TaskRun.__table__.create(engine, checkfirst=True)
    with SessionLocal() as db:
        row = TaskRun(kind=kind, status="running", state=dict(state))
        db.add(row)
        db.commit()
        return row.id


def update_task(task_id: int, state: dict) -> None:
    with SessionLocal() as db:
        row = db.get(TaskRun, task_id)
        if row is None:
            raise RuntimeError("No se encuentra la tarea persistida")
        row.state = dict(state)
        row.status = "running" if state.get("running") else state.get("phase", "finished")
        db.commit()


def recover_latest(kind: str) -> dict | None:
    """Called once at startup, before starting any workers."""
    with SessionLocal() as db:
        rows = db.scalars(select(TaskRun).where(
            TaskRun.kind == kind, TaskRun.status == "running"
        )).all()
        for row in rows:
            row.status = "interrupted"
            row.state = {
                **row.state, "running": False, "phase": "interrupted",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": "La tarea se interrumpió al reiniciar. Puedes volver a iniciarla.",
            }
        db.commit()
        latest = db.scalar(select(TaskRun).where(TaskRun.kind == kind).order_by(
            TaskRun.id.desc()
        ).limit(1))
        return {**latest.state, "task_id": latest.id} if latest else None
