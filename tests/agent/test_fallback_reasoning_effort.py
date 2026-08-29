from agent.auxiliary_client import _fallback_route_extra_body


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
