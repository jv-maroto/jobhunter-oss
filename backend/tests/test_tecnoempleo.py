"""Parser HTML de Tecnoempleo (fixture tomada del listado real, 2026-08)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.scrapers.tecnoempleo import (
    TecnoempleoScraper,
    company_from_url,
    parse_listing,
    query_slug,
)

CARD = """
<div class="col-12 col-sm-12 col-md-12 col-lg-9">
  <h1 class="h4 h6-xs text-center my-4">452 Ofertas Trabajo de python</h1>
  <a name="rf-727018e122303327ef45" id="rf-727018e122303327ef45"></a>
  <div class="p-3 border rounded mb-3 bg-white" style="cursor: pointer;">
    <div class="row fs--15">
      <div class="col-10 col-md-9 col-lg-7">
        <h3 class="fs-5 mb-2">
          <a href="https://www.tecnoempleo.com/senior-python-developer-gcp-appcast/google-cloud-platform/rf-727018e122303327ef45"
             class="font-weight-bold text-cyan-700" title="Senior Python Developer (GCP)">
            Senior Python Developer (GCP)
          </a>
        </h3>
        <span class="d-block d-lg-none text-gray-800"><b>Madrid</b> - 29/08/2026</span>
        <span class="hidden-md-down text-gray-800">
          <br>GFT es una compañía pionera en transformación digital. Teletrabajo 100%.<br>
          <span class="badge bg-danger text-white mx-1">Python</span>
          <span class="badge bg-gray-500 mx-1">Google Cloud Platform</span>
        </span>
      </div>
      <div class="col-12 col-lg-3 text-gray-700 pt-2 text-right hidden-md-down">
        29/08/2026<br><br><b>Madrid</b><br>Programador<br>
      </div>
    </div>
  </div>
</div>
"""


def test_parse_listing_extracts_card() -> None:
    jobs = parse_listing(CARD, "python")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Python Developer (GCP)"
    assert job.company == "Appcast"
    assert job.location == "Madrid"
    assert job.posted_at == datetime(2026, 8, 29, tzinfo=timezone.utc)
    assert job.remote is True
    assert "Python" in job.tags and "python" in job.tags
    assert job.source_url.endswith("rf-727018e122303327ef45")


def test_company_from_url_handles_reordered_titles() -> None:
    url = "https://www.tecnoempleo.com/backend-developer-python-hays/django-apis-rest/rf-abc"
    assert company_from_url(url, "Backend Developer Python") == "Hays"
    assert company_from_url(url, "Python Backend Developer") == "Hays"
    assert company_from_url("https://example.org/x", "Whatever") == "Tecnoempleo"


def test_query_slug_and_configure() -> None:
    assert query_slug("AI Engineer") == "ai-engineer"
    scraper = TecnoempleoScraper()
    scraper.configure(queries=["Backend Developer", "Backend Developer remote", "DevOps"])
    assert scraper.queries == ["Backend Developer", "DevOps"]
