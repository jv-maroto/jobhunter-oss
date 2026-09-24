"""Shared discovery policy: recent listings and preferred sources."""
from datetime import date, datetime, time, timedelta, timezone


def source_priority(source: str) -> int:
    return {"linkedin": 0, "indeed": 0, "tecnoempleo": 2}.get(source.lower(), 1)


def parse_posted_at(value: object) -> datetime | None:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return parse_posted_at(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            pass
    return None


def stale_listing(job: object, *, days: int = 30) -> bool:
    posted = (parse_posted_at(getattr(job, "posted_at", None))
              or parse_posted_at(getattr(job, "created_at", None)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if posted and posted < cutoff:
        return True
    text = (getattr(job, "description", "") or "").lower()
    return any(marker in text for marker in (
        "no longer accepting applications", "no longer available",
        "ya no se aceptan solicitudes", "ya no acepta solicitudes",
        "esta oferta ha caducado", "this job has expired",
        "this job is closed", "esta oferta ya no está disponible",
    ))
