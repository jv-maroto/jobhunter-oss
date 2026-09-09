import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from app.ai import keystore
from app.ai.providers.base import LLMError
from app.ai.providers.codex_provider import CodexProvider, codex_available
from app.ai.router import build_tier_map


def test_codex_routes_only_to_account(monkeypatch):
    monkeypatch.setattr(keystore, "get_state", lambda: {"ai_mode": "codex"})
    assert keystore.resolve_mode() == "codex"
    assert keystore.active_label() == "codex"
    assert build_tier_map("codex", "openai") == {
        tier: ["codex"] for tier in ("scoring", "generation", "messaging")
    }


@pytest.mark.parametrize("status,available", [("ChatGPT", True), ("API key", False)])
def test_requires_chatgpt_login(monkeypatch, status, available):
    monkeypatch.setattr("shutil.which", lambda _: "/bin/codex")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, "", f"Logged in using {status}",
    ))
    assert codex_available() is available


@pytest.mark.parametrize("failure", [None, "timeout", "exit", "json", "empty"])
def test_completion_contract(monkeypatch, failure):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    workspaces = []

    def run(command, **kwargs):
        assert command[-1] == "-"
        assert "--ignore-user-config" in command and "--ephemeral" in command
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert 'features.shell_tool=false' in command
        assert 'features.apps=false' in command
        assert 'web_search="disabled"' in command
        assert "OPENAI_API_KEY" not in kwargs["env"]
        assert "job data" in kwargs["input"]
        assert kwargs["timeout"] > 0
        workspaces.append(Path(kwargs["cwd"]))
        assert workspaces[-1].is_dir()
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        if failure == "exit":
            return subprocess.CompletedProcess(command, 1, "", "PRIVATE DIAGNOSTIC")
        events = [
            {"type": "item.completed", "item": {
                "type": "agent_message", "text": "bad JSON" if failure == "json" else '{"ok":true}',
            }},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 4}},
        ]
        output = "" if failure == "empty" else "\n".join(map(json.dumps, events))
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr("subprocess.run", run)
    call = CodexProvider().complete("Return JSON", "job data", json_mode=True)
    if failure:
        with pytest.raises(LLMError) as error:
            asyncio.run(call)
        assert "PRIVATE" not in str(error.value)
    else:
        response = asyncio.run(call)
        assert json.loads(response.content) == {"ok": True}
        assert response.provider == "codex"
        assert response.input_tokens == 10 and response.output_tokens == 4
        assert response.cost_eur == 0
    assert all(not path.exists() for path in workspaces)
