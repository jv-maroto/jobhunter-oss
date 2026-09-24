import uuid

import pytest

from app.db import SessionLocal, init_db
from app.models.application import Application
from app.models.job import Job


def test_application_keeps_original_listing_after_job_changes():
    init_db()
    with SessionLocal() as db:
        job = Job(title="Backend", company="Example", source="manual", source_url="https://example.com/job",
                  hash=uuid.uuid4().hex, description="Python and SQL")
        db.add(job)
        db.flush()
        application = Application(job_id=job.id)
        db.add(application)
        db.commit()
        original = dict(application.job_snapshot)
        job.description = "Position closed"
        db.commit()
        db.expire_all()
        assert application.job_snapshot == original
        assert application.job_snapshot["description"] == "Python and SQL"
        application.status = "submitted"
        db.commit()
        application.job_snapshot = {"description": "Rewritten"}
        with pytest.raises(ValueError, match="instantánea"):
            db.commit()
        db.rollback()
