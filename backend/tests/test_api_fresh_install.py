"""Comportamiento de una instalacion recien clonada (sin perfil)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_fresh_install_endpoints() -> None:
    with TestClient(app) as client:
        # /health returns status + capabilities + warnings — assert on the
        # essential contract, not exact equality (typst may or may not be in
        # the CI runner's PATH, which changes the warnings list).
        health = client.get("/health").json()
        assert health["status"] == "ok"
        assert "capabilities" in health
        assert isinstance(health.get("warnings", []), list)

        # Sin cv_master.json real -> el wizard debe dispararse.
        assert client.get("/onboarding/status").json() == {"onboarded": False}

        # Y NO se scrapea con la plantilla: 409 en las dos rutas de "buscar ahora".
        assert client.post("/jobs/scrape-now").status_code == 409
        assert client.post("/scrape/run").status_code == 409

        # El estado de IA expone si el modelo local esta descargado.
        ai = client.get("/settings/ai").json()
        for key in ("ai_mode", "has_key", "local_available", "local_model", "local_model_available"):
            assert key in ai
        assert ai["active"] == "off"

        # Listados vacios pero validos.
        assert client.get("/jobs").json() == {"total": 0, "items": []}
        assert client.get("/persons").json() == []
        assert client.get("/metrics/today").status_code == 200
