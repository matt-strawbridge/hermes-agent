"""Least-privilege tool policies for authorized Telegram private chats."""

from gateway.run import GatewayRunner
from plugins.platforms.telegram.adapter import TelegramAdapter


class _Config:
    def __init__(self, extra):
        self.extra = extra


class _Source:
    def __init__(self, *, chat_type="dm", user_id="200"):
        self.chat_type = chat_type
        self.user_id = user_id


def _adapter(extra):
    adapter = object.__new__(TelegramAdapter)
    adapter.config = _Config(extra)
    return adapter


def _runner(adapter):
    runner = object.__new__(GatewayRunner)
    runner._adapter_for_source = lambda source: adapter
    return runner


class TestTelegramDmToolsets:
    def test_collaborator_dm_gets_exact_narrow_policy(self):
        adapter = _adapter(
            {
                "dm_toolsets": ["web", "vision", "company_context", "  "],
                "dm_privileged_users": ["100"],
            }
        )
        assert adapter.toolsets_for_source(_Source(user_id="200")) == [
            "web",
            "vision",
            "company_context",
        ]

    def test_privileged_dm_uses_normal_telegram_surface(self):
        adapter = _adapter(
            {
                "dm_toolsets": ["web"],
                "dm_privileged_users": [100],
            }
        )
        assert adapter.toolsets_for_source(_Source(user_id="100")) is None

    def test_group_and_forum_routes_are_unchanged_without_policy(self):
        adapter = _adapter({"dm_toolsets": ["web"]})
        assert adapter.toolsets_for_source(_Source(chat_type="group")) is None
        assert adapter.toolsets_for_source(_Source(chat_type="forum")) is None

    def test_shared_routes_get_exact_policy_without_privileged_bypass(self):
        adapter = _adapter(
            {
                "group_toolsets": ["web", "vision", "company_context"],
                "dm_privileged_users": ["100"],
            }
        )
        expected = ["web", "vision", "company_context"]
        assert adapter.toolsets_for_source(
            _Source(chat_type="group", user_id="100")
        ) == expected
        assert adapter.toolsets_for_source(
            _Source(chat_type="forum", user_id="100")
        ) == expected
        assert adapter.toolsets_for_source(
            _Source(chat_type="channel", user_id="100")
        ) == expected

    def test_malformed_group_policy_fails_closed(self):
        adapter = _adapter({"group_toolsets": "web,file"})
        assert adapter.toolsets_for_source(_Source(chat_type="group")) == []

    def test_absent_dm_policy_preserves_legacy_behavior(self):
        assert _adapter({}).toolsets_for_source(_Source()) is None

    def test_empty_or_malformed_policy_fails_closed(self):
        assert _adapter({"dm_toolsets": []}).toolsets_for_source(_Source()) == []
        assert _adapter({"dm_toolsets": "web,file"}).toolsets_for_source(_Source()) == []

    def test_comma_separated_privileged_ids_are_supported(self):
        adapter = _adapter(
            {
                "dm_toolsets": ["web"],
                "dm_privileged_users": "100, 101",
            }
        )
        assert adapter.toolsets_for_source(_Source(user_id="101")) is None

    def test_dm_scratchpad_toolset_is_mounted_only_for_explicit_request(self):
        adapter = _adapter(
            {
                "dm_toolsets": ["web", "company_context"],
                "group_toolsets": ["web", "company_context"],
                "dm_scratchpad_toolsets": ["dm_scratchpads"],
            }
        )
        source = _Source(user_id="200")
        assert adapter.toolsets_for_source(
            source, prompt="what did we discuss somewhere?"
        ) == ["web", "company_context"]
        assert adapter.toolsets_for_source(
            source, prompt="Please search the DM scratchpads for lanterns"
        ) == ["web", "company_context", "dm_scratchpads"]
        assert adapter.toolsets_for_source(
            source, prompt="/dmsearch lanterns"
        ) == ["web", "company_context", "dm_scratchpads"]

    def test_buried_or_lane_only_text_does_not_mount_scratchpads(self):
        adapter = _adapter(
            {
                "dm_toolsets": ["web"],
                "dm_scratchpad_toolsets": ["dm_scratchpads"],
            }
        )
        source = _Source()
        buried = "Here is a long forwarded note. " + ("x" * 400) + (
            " search the DM scratchpads"
        )
        assert adapter.toolsets_for_source(source, prompt=buried) == ["web"]
        assert adapter.toolsets_for_source(
            source, prompt="The DM scratchpad is interesting"
        ) == ["web"]

    def test_privileged_explicit_policy_mounts_reader_without_losing_operator_tools(self):
        adapter = _adapter(
            {
                "dm_toolsets": ["web"],
                "dm_privileged_users": ["100"],
                "dm_scratchpad_toolsets": ["dm_scratchpads"],
                "dm_privileged_explicit_toolsets": [
                    "terminal", "file", "dm_scratchpads"
                ],
            }
        )
        source = _Source(user_id="100")
        assert adapter.toolsets_for_source(source, prompt="ordinary work") is None
        assert adapter.toolsets_for_source(
            source, prompt="Search the private bot threads for the idea"
        ) == ["terminal", "file", "dm_scratchpads"]


class TestEmptyRouteOverride:
    def test_empty_override_does_not_fall_back_to_platform_tools(self):
        adapter = _adapter({"dm_toolsets": []})
        runner = _runner(adapter)
        config = {
            "platform_toolsets": {
                "telegram": ["terminal", "file", "web"],
            }
        }
        resolved = GatewayRunner._resolve_enabled_toolsets_for_source(
            runner,
            config,
            _Source(),
            "telegram",
        )
        assert resolved == []
