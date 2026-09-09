from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai import cover_letter, cv_generator


@pytest.mark.parametrize("document_language", ["en", "es", "de", "fr", "it"])
def test_existing_cv_is_copied_exactly_without_generation(tmp_path, monkeypatch, document_language) -> None:
    monkeypatch.setattr(cv_generator.settings, "data_dir", str(tmp_path / "data"))
    resumes = cv_generator.settings.data_path / "resumes"
    resumes.mkdir()
    content = b"%PDF-1.7\nOriginal CV bytes \x00\xff\n%%EOF\n"
    source = resumes / "data-engineer-en.pdf"
    source.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    profile = {
        "application_documents": {
            "mode": "existing",
            "cv_by_track": {
                "data_engineer": {"filename": source.name, "sha256": digest, "language": document_language},
            },
        }
    }

    def no_generation():
        raise AssertionError("Existing CV mode must not call a provider or compiler")

    monkeypatch.setattr(cv_generator, "get_router", no_generation)
    monkeypatch.setattr(cv_generator, "_ensure_typst", no_generation)
    pdf, note, language = cv_generator.generate_cv(
        profile, {"track": "data_engineer"}, tmp_path / "application", "de-CH"
    )
    assert pdf.read_bytes() == source.read_bytes() == content
    assert language == document_language
    assert "copied unchanged" in note and digest in note
    assert not (pdf.parent / "cv.typ").exists()
    assert list(pdf.parent.iterdir()) == [pdf]


def test_existing_cv_invalid_configuration_fails_without_replacement(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cv_generator.settings, "data_dir", str(tmp_path / "data"))
    resumes = cv_generator.settings.data_path / "resumes"
    resumes.mkdir()
    content = b"%PDF-1.7\nOriginal CV\n%%EOF\n"
    (resumes / "valid.pdf").write_bytes(content)
    (resumes / "invalid.pdf").write_bytes(b"not a PDF")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(content)
    (resumes / "symlink.pdf").symlink_to(outside)
    base = {
        "filename": "valid.pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
        "language": "en",
    }
    cases = [
        ({"quant": {**base, "language": "unknown"}}, "requires a supported language"),
        ({}, "configured for role"),
        ({"quant": {**base, "filename": "../outside.pdf"}}, "basename"),
        ({"quant": {**base, "filename": "..\\outside.pdf"}}, "basename"),
        ({"quant": {**base, "filename": "missing.pdf"}}, "missing or unreadable"),
        ({"quant": {**base, "filename": "symlink.pdf"}}, "resumes directory"),
        ({"quant": {**base, "filename": "invalid.pdf"}}, "PDF header"),
        ({"quant": {**base, "sha256": None}}, "requires a valid SHA-256"),
        ({"quant": {**base, "sha256": "0" * 64}}, "failed SHA-256"),
    ]
    out = tmp_path / "application"
    out.mkdir()
    previous = out / "cv.pdf"
    previous.write_bytes(b"previous application artifact")

    def no_generation():
        raise AssertionError("Invalid existing CV configuration must not generate a replacement")

    monkeypatch.setattr(cv_generator, "get_router", no_generation)
    for mappings, message in cases:
        profile = {"application_documents": {"mode": "existing", "cv_by_track": mappings}}
        with pytest.raises(cv_generator.CVGenerationError, match=message):
            cv_generator.generate_cv(profile, {"track": "quant"}, out)
        assert previous.read_bytes() == b"previous application artifact"


def _profile() -> dict:
    return {
        "personal": {
            "name": 'Ada [Data] "{{TITLE}}"',
            "title": "Data & Analytics",
            "email": "ada@example.test",
            "location": "Bilbao",
            "github": 'https://example.test/ada?q="data"',
            "linkedin": "file:///etc/passwd",
        },
        "summary_en": "Data analyst with internship experience in reporting.",
        "summary_es": "Analista de datos con experiencia en prácticas de reporting.",
        "experience": [
            {
                "role": "Data Analyst Intern",
                "company": "Example",
                "start": "2025",
                "end": "2026",
                "highlights": ["Validated BI reports."],
            }
        ],
        "education": [
            {
                "degree": "Business Data Analytics",
                "institution": "Example University",
                "year": "2026",
            }
        ],
        "skills": {"Professional BI": ["SQL", "Qlik"], "Academic ML": ["pandas"]},
        "languages": [{"name": "German", "level": "Currently learning"}],
        "certifications": [
            {"name": "Analytics course", "issuer": "Example Academy", "year": "2025"}
        ],
        "projects": [
            {
                "name": "Dashboard",
                "description": "Sales analysis.",
                "context": "academic",
                "role_families": ["bi"],
            },
            {
                "name": "Risk model",
                "description": "Simulated portfolio risk.",
                "context": "academic",
                "role_families": ["quant"],
                "stack": ["Python"],
                "dates": "2026",
                "claim_boundaries": ["Evaluated on synthetic data only"],
            },
        ],
    }


def test_language_detection_and_explicit_swiss_locales() -> None:
    for text, language in [
        ("Requirements: experience in SQL", "en"),
        ("Requisitos: experiencia en datos", "es"),
        ("Ihre Aufgaben: Kenntnisse und Erfahrung. Wir bieten flexible Arbeit.", "de"),
        ("Votre profil: compétences et expérience. Nous offrons un poste.", "fr"),
        ("Requisiti: competenze ed esperienza. Offriamo un lavoro.", "it"),
        ("Data Analyst Zürich", "en"),
        ("", "en"),
        ("experience experiencia", "en"),
    ]:
        assert cv_generator._detect_language(text) == language
    for locale, language in [("de-CH", "de"), ("FR_ch", "fr"), ("it", "it")]:
        assert cv_generator._normalize_language(locale) == language
    with pytest.raises(ValueError, match="Document language"):
        cv_generator._normalize_language('en")[#read("/etc/passwd")]')


def test_source_fields_and_academic_claims_survive_fallback() -> None:
    profile = _profile()
    profile["experience"].append({"role": "Ended role", "start": "2020", "end": ""})
    source = cv_generator._basic_typst_from_master(
        profile, cv_generator._MINIMAL_TEMPLATE, "es", {"track": "quant"}
    )
    for expected in [
        profile["summary_es"],
        "Example University",
        "German - Currently learning",
        "Analytics course - Example Academy - 2025",
        "Academic ML",
        "Proyecto académico",
        "Evaluated on synthetic data only",
        "2025 - 2026",
        "Ended role - 2020",
    ]:
        assert expected in source
    assert "present" not in source
    assert "Risk model" in source
    assert "Dashboard" not in source
    assert "file:///etc/passwd" not in source
    assert "{{TITLE}}" in source
    assert cv_generator._date_range({"start": "2025", "current": True}) == "2025 - present"


def test_fallback_letter_has_only_profile_claims() -> None:
    profile = _profile()
    for language in ["en", "es", "de", "fr", "it"]:
        content = cover_letter._fallback_cover(
            profile,
            {"title": "Quant Analyst", "company": "Swiss Example", "track": "quant"},
            language,
        )
        assert "Data Analyst Intern" in content
        assert "Risk model" in content
        assert (
            "Proyecto académico" in content if language == "es" else "Academic project" in content
        )
        assert "Evaluated on synthetic data only" in content
        assert "Dashboard" not in content
        for invented in [
            "Full-Stack",
            "FastAPI",
            "React",
            "PostgreSQL",
            "Docker",
            "sysadmin",
            "production deployments",
            "work permit",
        ]:
            assert invented not in content
    empty = cover_letter._fallback_cover({}, {"title": "Analyst", "company": "Example"}, "en")
    assert "projects" not in empty
    assert "production" not in empty


def test_three_role_projects_are_selected_independently_of_input_order() -> None:
    unrelated = [{"name": f"Dashboard {i}", "role_families": ["bi"]} for i in range(15)]
    relevant = [
        {
            "name": name,
            "role_families": ["quant"],
            "context": "academic",
            "dates": "2024 - 2025",
            "context_detail": "Academic coursework in a five-person team.",
            "claim_boundaries": "Do not claim professional employment at the challenge sponsor.",
        }
        for name in [
            "Credit risk",
            "Monte Carlo option pricing",
            "Portfolio simulation",
            "Forecasting",
        ]
    ]
    profile = {"projects": unrelated + relevant}
    job = {
        "track": "quant",
        "title": "Quantitative Analyst",
        "description": "Monte Carlo option pricing and portfolio risk simulation",
    }
    selected = cv_generator._ranked_projects(profile, job)
    assert len(selected) == 3
    assert selected[0]["name"] == "Monte Carlo option pricing"
    assert all("quant" in project["role_families"] for project in selected)
    profile["projects"].reverse()
    assert cv_generator._ranked_projects(profile, job) == selected
    source = cv_generator._basic_typst_from_master(
        profile, cv_generator._MINIMAL_TEMPLATE, "en", job
    )
    assert "Dashboard" not in source
    assert "Forecasting" not in source
    assert "Academic coursework in a five-person team" in source
    assert "Do not claim" not in source
    assert source.count("2024 - 2025") == 3
    overlapping = {
        "context_detail": "Final degree project documented the same internship.",
        "description": "Duplicate internship metrics.",
        "claim_boundaries": "Overlaps the internship; do not count as separate employment.",
    }
    assert "Duplicate internship metrics" not in cv_generator._project_text(overlapping, "en")


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst compiler unavailable")
def test_real_pdf_pair_compiles_literal_text_and_falls_back_to_english(
    tmp_path, monkeypatch
) -> None:
    PdfReader = pytest.importorskip("pypdf").PdfReader

    profile = _profile()
    profile["experience"][0]["highlights"].append('#read("../private.txt") @citation $x$ [literal]')
    offline = SimpleNamespace(available_providers=lambda tier: [])
    monkeypatch.setattr(cv_generator, "get_router", lambda: offline)
    monkeypatch.setattr(cover_letter, "get_router", lambda: offline)
    template = Path(__file__).parents[1] / "app/data/cv_template.typ"
    monkeypatch.setattr(cv_generator.settings, "cv_template_path", str(template))
    job = {"title": "Quant Analyst", "company": "Example [Swiss]", "track": "quant"}
    cv_pdf, source, language = cv_generator.generate_cv(profile, job, tmp_path, "de-CH")
    cover_pdf, content = cover_letter.generate_cover_letter(profile, job, [], tmp_path, "de-CH")
    assert language == "en"
    for pdf in (cv_pdf, cover_pdf):
        assert pdf.read_bytes().startswith(b"%PDF")
        text = "\n".join(page.extract_text() for page in PdfReader(pdf).pages)
        assert 'read("../private.txt")' in text
        assert "ada@example.test" in text
        assert "Academic project" in text
    cv_text = "\n".join(page.extract_text() for page in PdfReader(cv_pdf).pages)
    assert "Example University" in cv_text
    assert "German - Currently learning" in cv_text
    assert "Kind regards" in "\n".join(page.extract_text() for page in PdfReader(cover_pdf).pages)
    assert "file:///etc/passwd" not in source
    assert content.startswith("I'm writing")
    monkeypatch.setattr(cv_generator.settings, "cv_template_path", str(tmp_path / "missing.typ"))
    minimal_pdf, _, _ = cv_generator.generate_cv({}, {}, tmp_path / "empty")
    assert PdfReader(minimal_pdf).pages


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst compiler unavailable")
def test_llm_typst_cannot_read_outside_output_root(tmp_path, monkeypatch) -> None:
    template = Path(__file__).parents[1] / "app/data/cv_template.typ"
    monkeypatch.setattr(cv_generator.settings, "cv_template_path", str(template))
    (tmp_path / "private.txt").write_text("PRIVATE_SENTINEL", encoding="utf-8")

    class Router:
        def available_providers(self, tier):
            return ["test"]

        async def complete_for(self, **kwargs):
            return SimpleNamespace(content='#read("../private.txt")')

    monkeypatch.setattr(cv_generator, "get_router", Router)
    with pytest.raises(cv_generator.CVGenerationError, match="project (root|sandbox)"):
        cv_generator.generate_cv({}, {}, tmp_path / "application")
    assert not (tmp_path / "application/cv.pdf").exists()
