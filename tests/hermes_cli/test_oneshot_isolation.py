from unittest.mock import patch

import hermes_cli.oneshot as oneshot


def test_no_tools_env_forces_explicit_empty_toolset(monkeypatch, capsys):
    captured = {}

    def fake_run_agent(prompt, **kwargs):
        captured.update(kwargs)
        return "OK", {"final_response": "OK"}

    monkeypatch.setenv("HERMES_ONESHOT_NO_TOOLS", "1")
    monkeypatch.setattr(oneshot, "_run_agent", fake_run_agent)

    assert oneshot.run_oneshot("summarize", toolsets="") == 0
    assert captured["toolsets"] == []
    assert captured["use_config_toolsets"] is False
    assert capsys.readouterr().out.strip() == "OK"


def test_run_agent_can_disable_tools_and_session_persistence(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self._session_messages = []

        def run_conversation(self, _prompt):
            return {"final_response": "OK"}

        def shutdown_memory_provider(self, *_args):
            pass

        def close(self):
            pass

    monkeypatch.setenv("HERMES_ONESHOT_NO_SESSION_PERSISTENCE", "1")
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "gpt-5.6-sol", "provider": "openai-codex"}},
    )
    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **_kwargs: {
            "api_key": "token",
            "base_url": "https://example.invalid",
            "provider": "openai-codex",
            "requested_provider": "openai-codex",
            "api_mode": "codex_responses",
            "credential_pool": None,
        },
    )
    monkeypatch.setattr(
        "hermes_cli.mcp_startup.ensure_mcp_discovery_before_agent_build",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr("run_agent.AIAgent", FakeAgent)
    monkeypatch.setattr(
        oneshot,
        "_create_session_db_for_oneshot",
        lambda: (_ for _ in ()).throw(AssertionError("must not open SessionDB")),
    )

    response, result = oneshot._run_agent(
        "summarize",
        model="gpt-5.6-sol",
        provider="openai-codex",
        toolsets=[],
        use_config_toolsets=False,
    )

    assert response == "OK"
    assert result["final_response"] == "OK"
    assert captured["enabled_toolsets"] == []
    assert captured["session_db"] is None
