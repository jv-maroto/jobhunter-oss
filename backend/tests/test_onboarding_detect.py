"""Deteccion de primer uso: plantilla => no onboarded; nombre real o marcador => onboarded."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from app.config import settings
from app.onboarding import detect


@pytest.fixture
def clean_profile() -> Iterator[None]:
    """Deja la instancia como recien clonada al terminar (otros tests lo asumen)."""
    yield
    for p in (settings.cv_master_file, settings.onboarding_marker_file):
        if p.exists():
            p.unlink()


def _write_cv(data: dict) -> None:
    settings.cv_master_file.parent.mkdir(parents=True, exist_ok=True)
    settings.cv_master_file.write_text(json.dumps(data), encoding="utf-8")


def test_missing_cv_is_not_onboarded(clean_profile: None) -> None:
    assert detect.is_onboarded() is False


def test_template_is_not_onboarded(clean_profile: None) -> None:
    _write_cv({"_README": "template", "personal": {"name": "Your Full Name"}})
    assert detect.is_onboarded() is False


def test_real_name_is_onboarded(clean_profile: None) -> None:
    _write_cv({"personal": {"name": "Ada Lovelace"}})
    assert detect.is_onboarded() is True


def test_marker_wins(clean_profile: None) -> None:
    _write_cv({"_README": "template", "personal": {"name": ""}})
    detect.mark_onboarded()
    assert detect.is_onboarded() is True
