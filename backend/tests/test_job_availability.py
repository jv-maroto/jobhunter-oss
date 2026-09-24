import asyncio

from app import job_availability as availability


def test_posted_date_is_not_expiration_and_ats_presence_is_explicit():
    job = {"posted_at": "2020-01-01", "description": "Apply now"}
    assert availability.assess_listing(job)["status"] == "unverified"
    assert availability.assess_listing(job, ats_present=True)["status"] == "active"
    assert availability.assess_listing({**job, "validThrough": "2020-01-01"}, ats_present=True)["status"] == "expired"
    assert availability.assess_listing({"description": "This job is closed"})["status"] == "expired"


def test_http200_without_matching_job_is_not_active_and_jsonld_expiration():
    job = {"title": "Python Developer"}
    assert availability.assess_document(job, "<h1>Welcome</h1>")["status"] == "unverified"
    for title, deadline, status in [("Other role", "2099-01-01", "unverified"), ("Python Developer", "2020-01-01", "expired"), ("Python Developer", "2099-01-01", "active")]:
        html = '<script type="application/ld+json">{"@type":"JobPosting","title":"' + title + '","validThrough":"' + deadline + '"}</script>'
        assert availability.assess_document(job, html)["status"] == status
    assert availability.assess_document(job, "<h1>This job has expired</h1>")["status"] == "expired"


def test_safe_reader_errors_are_distinguished_and_no_new_fetcher(monkeypatch):
    for message, status in [("Fuente no disponible (HTTP 404)", "expired"), ("Fuente no disponible (HTTP 410)", "expired"), ("Fuente no disponible (HTTP 403)", "unverified"), ("Solo se admiten fuentes HTTPS públicas sin credenciales", "unverified")]:
        def fetch(url):
            raise ValueError(message)
        monkeypatch.setattr(availability, "fetch_public_document", fetch)
        checked = asyncio.run(availability.check_listing({"source_url": "https://example.com/job"}))
        assert checked["status"] == status


def test_batch_preserves_unknown_limits_checks_and_ats_needs_no_network(monkeypatch):
    calls = []
    def fetch(url):
        calls.append(url)
        return "<h1>Jobs</h1>", "text/html", url
    monkeypatch.setattr(availability, "fetch_public_document", fetch)
    jobs = [{"url": "https://example.com/" + str(index)} for index in range(12)]
    checked = asyncio.run(availability.verify_scraped_jobs(jobs, max_checks=3))
    assert len(checked) == 12 and len(calls) == 3
    assert all(result["status"] == "unverified" for _, result in checked)
    calls.clear()
    assert all(result["status"] == "active" for _, result in asyncio.run(availability.verify_scraped_jobs(jobs, ats_present=True)))
    assert calls == []


def test_timeout_keeps_network_slots_until_workers_finish(monkeypatch):
    import threading

    release = threading.Event()
    calls = []
    def slow_fetch(url):
        calls.append(url)
        assert release.wait(1)
        return "<h1>Jobs</h1>", "text/html", url
    async def immediate_timeout(task, timeout):
        await asyncio.sleep(0.01)
        raise TimeoutError
    monkeypatch.setattr(availability, "fetch_public_document", slow_fetch)
    monkeypatch.setattr(availability.asyncio, "wait_for", immediate_timeout)
    async def scenario():
        try:
            one = await availability.check_listing({"url": "https://example.com/1"})
            two = await availability.check_listing({"url": "https://example.com/2"})
            three = await availability.check_listing({"url": "https://example.com/3"})
            assert one["evidence"] == two["evidence"] == "timeout"
            assert three["evidence"] == "verification_busy"
            assert len(calls) == 2
        finally:
            release.set()
            await asyncio.sleep(0.02)
    asyncio.run(scenario())


def test_effective_availability_ages_evidence_without_mutating_check_time():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    old = {"status": "active", "checked_at": (now - timedelta(days=2)).isoformat(), "expires_at": "2099-01-01"}
    effective = availability.effective_availability(old)
    assert effective["status"] == "unverified"
    assert effective["checked_at"] == old["checked_at"] and old["status"] == "active"
    expired = {"status": "active", "checked_at": now.isoformat(), "expires_at": "2020-01-01"}
    assert availability.effective_availability(expired)["status"] == "expired"
    fresh = {"status": "active", "checked_at": now.isoformat()}
    assert availability.effective_availability(fresh)["status"] == "active"
    assert availability.effective_availability(None) is None
    assert availability.effective_availability({"status": "active"})["status"] == "unverified"


def test_conditional_closure_and_other_employer_posting_are_not_evidence():
    assert availability.assess_listing({"description": "If this position is closed please subscribe to alerts."})["status"] == "unverified"
    assert availability.assess_listing({"description": "This position is closed. Subscribe to alerts."})["status"] == "expired"
    html = '<script type="application/ld+json">{"@type":"JobPosting","title":"Engineer","hiringOrganization":{"name":"Other"},"validThrough":"2099-01-01"}</script>'
    assert availability.assess_document({"title": "Engineer", "company": "Demo"}, html)["status"] == "unverified"
    html = '<script type="application/ld+json">{"@type":"JobPosting","title":"Engineer","url":"https://example.com/other","validThrough":"2099-01-01"}</script>'
    assert availability.assess_document({"title": "Engineer", "url": "https://example.com/current"}, html)["status"] == "unverified"


def test_indeed_requires_fresh_positive_evidence_and_recognizes_expiration_text():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    job = SimpleNamespace(source="indeed", source_url="https://es.indeed.com/viewjob?jk=1", availability=None)
    assert availability.needs_indeed_verification(job)
    job.availability = {"status":"active", "checked_at":datetime.now(timezone.utc).isoformat()}
    assert not availability.needs_indeed_verification(job)
    job.availability["checked_at"] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    assert availability.needs_indeed_verification(job)
    job.source = "manual"
    assert availability.needs_indeed_verification(job)
    assert availability.assess_document({"title":"Engineer"}, "<h1>Esta oferta de empleo ha caducado en Indeed</h1>")["status"] == "expired"
    assert availability.assess_document({"title":"Engineer"}, "<h1>This job posting has expired</h1>")["status"] == "expired"
