from agent.tool_executor import _inject_authenticated_dm_scratchpad_requester
from gateway.session_context import reset_session_vars, set_session_vars


def test_authenticated_context_overrides_model_supplied_requester():
    tokens = set_session_vars(user_id="832202205", user_name="Matt Satterberg")
    try:
        result = _inject_authenticated_dm_scratchpad_requester(
            "mcp__dm_scratchpads__search_dm_scratchpads",
            {"query": "lantern", "requester": "Fake Admin"},
        )
    finally:
        reset_session_vars(tokens)
    assert result["requester"] == "Matt Satterberg (832202205)"


def test_missing_authenticated_context_fails_closed_to_empty_actor():
    result = _inject_authenticated_dm_scratchpad_requester(
        "mcp__dm_scratchpads__read_dm_scratchpad",
        {"archive_message_id": "dm-1", "requester": "Fake Admin"},
    )
    assert result["requester"] == ""


def test_unrelated_tools_are_unchanged():
    args = {"requester": "model value"}
    assert _inject_authenticated_dm_scratchpad_requester("web_search", args) is args
