#!/usr/bin/env python3
"""Back up local Docker volumes and verify restoration without touching live data.

Stop backend writers before running for consistency between SQLite and documents.
Credential files (.env, token/secret filenames) are excluded. The database is an
exact recovery copy and may contain sensitive settings. Keep archives private.
"""

import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    database = root / "backend/data/jobhunter.db"
    if not database.is_file():
        raise SystemExit("No se encuentra la base del volumen Docker backend/data/jobhunter.db")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    entries = {}
    skipped = []
    with tempfile.TemporaryDirectory(prefix="jobslave-backup-check-") as temp:
        copied = Path(temp) / "jobhunter.db"
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as source:
            with sqlite3.connect(copied) as target:
                source.backup(target)
                assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                counts = {
                    name: target.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                    for (name,) in target.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
        with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as archive:
            args.output.chmod(0o600)
            for folder in ("backend/data", "backend/app/data", "cvs-out"):
                for path in sorted((root / folder).rglob("*")):
                    if not path.is_file() or path.is_symlink():
                        continue
                    relative = path.relative_to(root).as_posix()
                    lower = path.name.lower()
                    if path == database or lower.endswith((".db-wal", ".db-shm")):
                        continue
                    if any(word in lower for word in ("token", "secret", "credential")) or lower.startswith(".env"):
                        skipped.append(relative)
                        continue
                    content = path.read_bytes()
                    archive.writestr(relative, content)
                    entries[relative] = digest(content)
            content = copied.read_bytes()
            archive.writestr("backend/data/jobhunter.db", content)
            entries["backend/data/jobhunter.db"] = digest(content)
            archive.writestr("manifest.json", json.dumps({
                "version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "files": entries, "table_counts": counts,
                "excluded_credentials": skipped,
                "scope": "Docker bind volumes; reconfigure credentials and any external custom paths",
            }, indent=2))
        # Restore into an isolated directory and verify bytes and database content.
        restored = Path(temp) / "restore"
        with zipfile.ZipFile(args.output) as archive:
            for name, expected in entries.items():
                content = archive.read(name)
                assert digest(content) == expected, name
                target = restored / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        with sqlite3.connect(restored / "backend/data/jobhunter.db") as check:
            assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            for name, expected in counts.items():
                assert check.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] == expected
    args.output.chmod(0o600)
    print(json.dumps({"archive": str(args.output), "files_verified": len(entries),
                      "tables_verified": len(counts), "restore": "verified in isolated directory",
                      "excluded_credential_files": len(skipped)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
