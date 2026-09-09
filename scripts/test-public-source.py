import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


spec = importlib.util.spec_from_file_location("public_source", Path(__file__).with_name("check-public-source.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


with tempfile.TemporaryDirectory(prefix="jobhunter-public-source-") as directory:
    root = Path(directory)
    subprocess.run(["git", "init", "-q", directory], check=True)
    (root / ".gitignore").write_text("output/\n.env*\n!.env.example\nbackend/data/\nbackend/app/data/cv_master.json\n")
    (root / "README.md").write_text("Synthetic contact: user@example.com\n")
    (root / ".env.example").write_text("OPENAI_API_KEY=\n")
    (root / "public.pdf").write_bytes(b"%PDF-1.4\nPublic reference asset\n")
    (root / "output").mkdir()
    (root / "output/private.pdf").write_bytes(b"private export")
    assert list(checker.scan(root)) == []

    subprocess.run(["git", "-C", directory, "add", "."], check=True)
    token = "sk-" + "testcredential" * 3
    (root / "README.md").write_text(token)
    assert any(f[2] == "credential-pattern" for f in checker.scan(root))
    assert list(checker.scan(root, staged=True)) == []
    subprocess.run(["git", "-C", directory, "add", "README.md"], check=True)
    (root / "README.md").write_text("clean working tree")
    assert any(f[2] == "credential-pattern" for f in checker.scan(root, staged=True))
    subprocess.run(["git", "-C", directory, "add", "README.md"], check=True)

    home = "/home/" + "fixture-person/project"
    (root / "local-link").symlink_to(home)
    assert any(f[2] == "absolute-symlink" for f in checker.scan(root))
    (root / "local-link").unlink()
    (root / "links").mkdir()
    (root / "links/outside").symlink_to("../../escaped")
    subprocess.run(["git", "-C", directory, "add", "links/outside"], check=True)
    (root / "links/outside").unlink()
    (root / "links").rmdir()
    (root / "links").symlink_to("nested/directory")
    assert any(f[2] == "external-symlink" for f in checker.scan(root, staged=True))
    subprocess.run(["git", "-C", directory, "rm", "--cached", "-q", "links/outside"], check=True)
    (root / "links").unlink()
    (root / "notes.txt").write_text(home)
    assert any(f[2] == "local-home-path" for f in checker.scan(root))
    (root / "notes.txt").unlink()

    subprocess.run(["git", "-C", directory, "add", "-f", "output/private.pdf"], check=True)
    assert any(f[2] == "private-artifact" for f in checker.scan(root, staged=True))
    subprocess.run(["git", "-C", directory, "rm", "--cached", "-q", "output/private.pdf"], check=True)
    for path in ("backend/custom.db-wal", "backend/custom.db-shm", ".env.production", "backend/runtime.log"):
        assert checker.private_path(path)

    (root / "backend/app/data").mkdir(parents=True)
    contact = "synthetic.person@" + "example.test"
    profile = root / "backend/app/data/cv_master.json"
    profile.write_text(json.dumps({"_README": "template instructions", "personal": {"email": contact},
                                   "experience": [{"company": "Synthetic Employer"}],
                                   "education": [{"institution": "ABC"}],
                                   "projects": [{"name": "Synthetic Project"}]}))
    (root / "backend/.env").write_text("SERVICE_API_KEY=" + token)
    integrations = root / "backend/data/integrations"
    integrations.mkdir(parents=True)
    (integrations / "test.json").write_text(json.dumps({"token_type": "Bearer", "password": "p!n7"}))
    values = checker.private_values(root)
    assert contact in values and token in values
    assert "p!n7" in values and "Bearer" not in values
    assert {"Synthetic Employer", "ABC", "Synthetic Project"} <= values
    assert checker.contains_private('school: "ABC"', "ABC")
    assert not checker.contains_private("alphabetabcdef", "ABC")
    assert "STRASSE" not in checker.safe_name("STRASSE PERSON.txt", {"Straße Person"})
    (root / "notes.txt").write_text(contact)
    assert any(f[2] == "private-config-value" for f in checker.scan(root, values=values))

    previous = Path.cwd()
    argv = sys.argv
    try:
        os.chdir(root)
        sys.argv = ["check-public-source.py", "--with-private-values"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            assert checker.main() == 1
        assert contact not in output.getvalue() and token not in output.getvalue()
        profile.write_text("{broken")
        with contextlib.redirect_stdout(io.StringIO()):
            assert checker.main() == 2
    finally:
        os.chdir(previous)
        sys.argv = argv

print("PASS: synthetic public-source checks (working tree, staged bytes, private data, redaction).")
