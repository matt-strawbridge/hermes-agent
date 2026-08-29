from types import SimpleNamespace

from run_agent import AIAgent


def test_blocked_warning_reemits_when_real_usage_becomes_critical():
    emitted = []
    fake = SimpleNamespace(
        context_compressor=SimpleNamespace(
            last_real_prompt_tokens=100_000,
            context_length=272_000,
        ),
        _last_ctx_overflow_warn=None,
        _emit_warning=emitted.append,
        _touch_activity=lambda *_args, **_kwargs: None,
    )

    AIAgent._warn_context_overflow_blocked(
        fake, "cooldown:30", 210_000, 200_000
    )
    assert len(emitted) == 1
    assert "HERMES_CONTEXT_CRITICAL" not in emitted[-1]

    fake.context_compressor.last_real_prompt_tokens = 240_000
    AIAgent._warn_context_overflow_blocked(
        fake, "cooldown:20", 225_000, 200_000
    )
    assert len(emitted) == 2
    assert emitted[-1].startswith("[[HERMES_CONTEXT_CRITICAL]]")
