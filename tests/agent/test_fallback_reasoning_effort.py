from types import SimpleNamespace
from unittest.mock import patch

from agent.auxiliary_client import (
    _build_call_kwargs,
    _call_llm_impl,
    _fallback_route_extra_body,
)


def test_fallback_reasoning_effort_overrides_task_level_effort():
    result = _fallback_route_extra_body(
        {"reasoning_effort": "high"},
        {"reasoning": {"enabled": True, "effort": "low"}, "other": 1},
    )
    assert result == {
        "reasoning": {"enabled": True, "effort": "high"},
        "other": 1,
    }


def test_explicit_entry_reasoning_body_wins_over_shorthand():
    result = _fallback_route_extra_body(
        {
            "reasoning_effort": "high",
            "extra_body": {
                "reasoning": {"enabled": True, "effort": "medium"},
            },
        },
        {"reasoning": {"enabled": True, "effort": "low"}},
    )
    assert result["reasoning"]["effort"] == "medium"


def test_invalid_effort_does_not_destroy_task_defaults():
    base = {"reasoning": {"enabled": True, "effort": "low"}}
    assert _fallback_route_extra_body(
        {"reasoning_effort": "not-real"}, base
    ) == base


def test_route_scoped_reasoning_does_not_leak_to_main_agent_fallback():
    task_body = {"reasoning": {"enabled": True, "effort": "low"}}
    route_body = {"reasoning": {"enabled": True, "effort": "high"}}
    captured = {}
    primary_client = SimpleNamespace(
        base_url="https://fallback.invalid",
        chat=SimpleNamespace(completions=SimpleNamespace()),
    )
    main_client = SimpleNamespace(base_url="https://chatgpt.invalid")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
    )

    def capture_fallback(*_args, **kwargs):
        captured["extra_body"] = kwargs["effective_extra_body"]
        return response

    with patch(
        "agent.auxiliary_client._resolve_task_provider_model",
        return_value=("custom", "bad-model", "", "key", None),
    ), patch(
        "agent.auxiliary_client._get_task_extra_body",
        return_value=task_body,
    ), patch(
        "agent.auxiliary_client._get_cached_client",
        return_value=(primary_client, "bad-model"),
    ), patch(
        "agent.auxiliary_client._build_call_kwargs",
        return_value={"messages": [{"role": "user", "content": "x"}]},
    ), patch(
        "agent.auxiliary_client._relay_sync_completion",
        side_effect=ConnectionError("route down"),
    ), patch(
        "agent.auxiliary_client._try_configured_fallback_chain",
        return_value=(None, None, ""),
    ), patch(
        "agent.auxiliary_client._try_main_agent_model_fallback",
        return_value=(main_client, "gpt-5.6-sol", "main-agent(openai-codex)"),
    ), patch(
        "agent.auxiliary_client._call_fallback_candidate_sync",
        side_effect=capture_fallback,
    ):
        result = _call_llm_impl(
            task="compression",
            provider="custom",
            model="bad-model",
            messages=[{"role": "user", "content": "x"}],
            route_extra_body=route_body,
        )

    assert result is response
    assert captured["extra_body"] == task_body


def test_native_anthropic_honors_explicit_digest_output_cap():
    kwargs = _build_call_kwargs(
        "anthropic",
        "claude-opus-5",
        [{"role": "user", "content": "digest"}],
        max_tokens=1_400,
        base_url="https://api.anthropic.com",
        task="compression",
    )
    assert kwargs.get("max_tokens") == 1_400
