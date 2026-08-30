"""Aisla los tests del estado real del usuario.

`app.config.Settings` se instancia al importar `app.config`, asi que las
variables de entorno deben fijarse ANTES de importar cualquier cosa de `app`.
Todo (DB, data/, cv_master.json, marcador de onboarding) va a un directorio
temporal: los tests nunca tocan `backend/jobhunter.db` ni tu perfil.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="jobhunter-tests-"))

os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ["CV_MASTER_PATH"] = str(TMP / "cv_master.json")
os.environ["ONBOARDING_MARKER_PATH"] = str(TMP / "data" / ".onboarded")
os.environ["ONBOARDING_DRAFT_PATH"] = str(TMP / "data" / "onboarding_draft.json")
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["AI_MODE"] = "off"
os.environ["LOG_LEVEL"] = "warning"
