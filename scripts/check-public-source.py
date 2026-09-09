#!/usr/bin/env python3
"""Read-only publication check. Reports locations/categories, never matched values."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
import re
import shlex
import subprocess


SECRET = re.compile(
    r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{30,}"
    r"|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
HOME = re.compile(r"/(?:home|Users)/([^/\s`\"']+)|[A-Za-z]:[\\/]Users[\\/]([^\\/\s`\"']+)")
PLACEHOLDER = re.compile(r"^(?:you|user|username|example|\.\.\.|<[^>]+>|\$\{[^}]+\})$")
CREDENTIAL_FIELD = re.compile(r"(?:^|[_.])(?:key|token|secret|password|cookie|account|email)$|(?:^|\.)keys\.", re.I)
PERSONAL_FIELDS = {"name", "email", "phone", "github", "linkedin", "portfolio"}


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)


def private_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        path.parts[0] in {"output", ".codegraph"}
        or name.startswith(("backend/data/", "backend/app/data/cv_master_backups/"))
        or name == "backend/app/data/cv_master.json"
        or (name.startswith("cvs-out/") and name != "cvs-out/README.md")
        or ((path.name == ".env" or path.name.startswith(".env.")) and not path.name.endswith(".example"))
        or bool(re.search(r"\.(?:db|sqlite3?)(?:-(?:wal|shm|journal))?$|\.log(?:\..*)?$", path.name))
    )


def contains_private(text: str, value: str) -> bool:
    text, value = text.casefold(), value.casefold()
    return bool(re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text)) if len(value) < 8 else value in text


def content_issues(text: str, private_values: set[str]):
    for line, value in enumerate(text.splitlines(), 1):
        if SECRET.search(value):
            yield line, "credential-pattern"
        if any(not PLACEHOLDER.fullmatch(match.group(1) or match.group(2)) for match in HOME.finditer(value)):
            yield line, "local-home-path"
        if any(contains_private(value, secret) for secret in private_values):
            yield line, "private-config-value"


def private_values(root: Path) -> set[str]:
    values: set[str] = set()
    env: dict[str, str] = {}

    def remember(value):
        if isinstance(value, str) and value.strip():
            values.add(value.strip())

    for path in (root / ".env", root / "backend/.env", root / "frontend/.env.local"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            key, separator, value = line.removeprefix("export ").partition("=")
            if separator and not key.lstrip().startswith("#"):
                parts = shlex.split(value, comments=True)
                value = " ".join(parts)
                env[key.strip().upper()] = value
                if CREDENTIAL_FIELD.search(key):
                    remember(value)

    def configured(key: str, default: str) -> Path:
        return root / "backend" / Path(os.environ.get(key, env.get(key, default))).expanduser()

    profile = configured("CV_MASTER_PATH", "app/data/cv_master.json")
    if profile.exists():
        cv = json.loads(profile.read_text())
        for key, value in cv.get("personal", {}).items():
            if key in PERSONAL_FIELDS:
                remember(value)
                if key == "name" and isinstance(value, str):
                    remember(value.replace(" ", "_"))
                    remember(value.replace(" ", "-"))
        for section, fields in (("experience", ("company",)), ("education", ("institution", "school")),
                                ("projects", ("name", "title")), ("projects_highlight", ("name", "title"))):
            for record in cv.get(section) or []:
                if isinstance(record, dict):
                    for field in fields:
                        remember(record.get(field))

    def credentials(value, key=""):
        if isinstance(value, dict):
            for field, item in value.items():
                credentials(item, key + "." + field)
        elif isinstance(value, list):
            for item in value:
                credentials(item, key)
        elif CREDENTIAL_FIELD.search(key):
            remember(value)

    data = configured("DATA_DIR", "data")
    for path in (data / "integrations").glob("*.json"):
        credentials(json.loads(path.read_text()))
    token = data / "ext_token.txt"
    if token.exists():
        remember(token.read_text())
    return values


def candidates(root: Path, staged: bool):
    if staged:
        for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            metadata, name = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode().split()
            name = os.fsdecode(name)
            if stage != "0" or mode == "160000":
                yield name, b"", "unresolved-or-submodule"
            else:
                yield name, git(root, "cat-file", "blob", oid), "symlink" if mode == "120000" else "file"
    else:
        names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        for raw in sorted(set(names.split(b"\0")) - {b""}):
            name = os.fsdecode(raw)
            path = root / name
            if path.is_symlink():
                yield name, os.fsencode(os.readlink(path)), "symlink"
            elif not path.resolve().is_relative_to(root.resolve()):
                yield name, b"", "external-symlink"
            elif path.is_file():
                yield name, path.read_bytes(), "file"
            elif path.exists():
                yield name, b"", "unresolved-or-submodule"


def scan(root: Path, staged: bool = False, values: set[str] | None = None):
    values = values or set()
    for name, data, kind in candidates(root, staged):
        if private_path(name):
            yield name, 0, "private-artifact"
        for _, category in content_issues(name, values):
            yield name, 0, category
        if kind in {"unresolved-or-submodule", "external-symlink"}:
            yield name, 0, kind
            continue
        if kind == "symlink":
            target = os.fsdecode(data)
            lexical_target = posixpath.normpath(str(PurePosixPath(name).parent / target.replace("\\", "/")))
            if PurePosixPath(target).is_absolute() or PureWindowsPath(target).is_absolute():
                yield name, 0, "absolute-symlink"
            elif lexical_target == ".." or lexical_target.startswith("../"):
                yield name, 0, "external-symlink"
        # ponytail: plain bytes only; review compressed PDF/image content with document tools.
        for line, category in content_issues(data.decode("utf-8", errors="replace"), values):
            yield name, line, category


def safe_name(name: str, values: set[str]) -> str:
    if private_path(name):
        return "[private artifact path]"
    if any(contains_private(name, value) for value in values):
        return "[private value in path]"
    name = SECRET.sub("[redacted]", HOME.sub("[local home]", name))
    return json.dumps(name, ensure_ascii=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Check the complete Git index, using staged bytes.")
    parser.add_argument("--with-private-values", action="store_true", help="Also compare local profile/contact/credential values; requires local config only.")
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
        values = private_values(root) if args.with_private_values else set()
        findings = sorted(set(scan(root, args.staged, values)))
    except (OSError, ValueError, TypeError, AttributeError, subprocess.CalledProcessError):
        print("FAIL: unable to read candidate or private configuration; details withheld.")
        return 2
    for name, line, category in findings:
        print(f"{safe_name(name, values)}:{line}: {category}")
    mode = "index" if args.staged else "tracked + eligible untracked working tree"
    print(f"{'FAIL' if findings else 'PASS'}: {mode}; {len(findings)} finding(s). No files changed.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
