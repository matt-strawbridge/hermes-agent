"""Tests for lightweight persistent-lane session-continuity hints.

Salvaged from PR #36220 (metamon-p), ported onto the current SessionStore.

Covers:
- SessionStore records the previous session_id on auto-reset (and only then).
- prev_session_id survives a to_dict() → from_dict() roundtrip (gateway restart).
- build_channel_continuity_note() emits a hint only for supported persistent lanes
  that were auto-reset with real prior activity, and stays silent otherwise.
"""

from datetime import datetime, timedelta

import pytest

from gateway.config import GatewayConfig, Platform, SessionResetPolicy
from gateway.session import (
    SessionEntry,
    SessionSource,
    SessionStore,
    build_channel_continuity_note,
)


@pytest.fixture()
def _isolated_db(tmp_path, monkeypatch):
    import hermes_state

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", tmp_path / "state.db")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _make_store(tmp_path, policy=None):
    config = GatewayConfig()
    if policy:
        config.default_reset_policy = policy
    return SessionStore(sessions_dir=tmp_path / "sessions", config=config)


def _slack_source(thread_id=None):
    return SessionSource(
        platform=Platform.SLACK,
        chat_id="C123",
        chat_type="thread" if thread_id else "channel",
        user_id="U1",
        thread_id=thread_id,
    )


def _telegram_source(thread_id="6"):
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-100123",
        chat_type="group",
        user_id=None,
        thread_id=thread_id,
    )


# ---------------------------------------------------------------------------
# SessionStore records prev_session_id on auto-reset
# ---------------------------------------------------------------------------

class TestPrevSessionIdCapture:
    def test_prev_session_id_set_on_auto_reset(self, _isolated_db, tmp_path):
        store = _make_store(tmp_path, SessionResetPolicy(mode="idle", idle_minutes=1))
        source = _slack_source(thread_id="T9")

        entry1 = store.get_or_create_session(source)
        assert entry1.prev_session_id is None  # fresh session, nothing replaced

        entry1.last_prompt_tokens = 4000  # had real conversation
        entry1.updated_at = datetime.now() - timedelta(minutes=5)
        store._save()

        entry2 = store.get_or_create_session(source)
        assert entry2.was_auto_reset is True
        assert entry2.reset_had_activity is True
        assert entry2.prev_session_id == entry1.session_id


# ---------------------------------------------------------------------------
# build_channel_continuity_note
# ---------------------------------------------------------------------------

def _reset_entry(platform, prev="20260101_000000_abc", had_activity=True):
    return SessionEntry(
        session_key="k",
        session_id="20260101_010000_def",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=platform,
        was_auto_reset=True,
        auto_reset_reason="daily",
        reset_had_activity=had_activity,
        prev_session_id=prev,
    )


class TestBuildChannelContinuityNote:
    def test_slack_channel_emits_hint(self):
        entry = _reset_entry(Platform.SLACK)
        note = build_channel_continuity_note(entry, _slack_source())
        assert note is not None
        assert "session_search" in note
        assert entry.prev_session_id in note
        assert "channel" in note

    def test_telegram_topic_emits_hint(self):
        entry = _reset_entry(Platform.TELEGRAM)
        note = build_channel_continuity_note(entry, _telegram_source())
        assert note is not None
        assert "session_search" in note
        assert entry.prev_session_id in note
        assert "topic" in note

    def test_injects_bounded_prior_state_of_play(self, _isolated_db):
        entry = _reset_entry(Platform.TELEGRAM)
        memo_dir = _isolated_db / "continuity" / "by-session"
        memo_dir.mkdir(parents=True)
        (memo_dir / f"{entry.prev_session_id}.md").write_text(
            "The live crux is preserving latent commitments.",
            encoding="utf-8",
        )

        note = build_channel_continuity_note(entry, _telegram_source())

        assert "Prior-session state of play" in note
        assert "UNTRUSTED bot-authored context" in note
        assert "fence=" in note
        assert "End prior-session state of play fence=" in note
        assert "preserving latent commitments" in note
        assert "session_search" in note

    def test_unsafe_previous_session_id_is_rejected(self):
        entry = _reset_entry(Platform.TELEGRAM, prev="../../escape")
        assert build_channel_continuity_note(entry, _telegram_source()) is None


    def test_no_activity_returns_none(self):
        entry = _reset_entry(Platform.SLACK, had_activity=False)
        assert build_channel_continuity_note(entry, _slack_source()) is None
