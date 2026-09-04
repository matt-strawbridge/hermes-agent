from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter


ROSTER = "[Alice](tg://user?id=1) [Bob](tg://user?id=2)"


def _adapter():
    config = PlatformConfig(
        enabled=True,
        token="test",
        extra={
            "literal_trigger_replies": [
                {
                    "chat_id": "-100123",
                    "thread_id": "1",
                    "trigger": "@all",
                    "reply": ROSTER,
                }
            ]
        },
    )
    adapter = TelegramAdapter(config)
    adapter._bot = SimpleNamespace(send_message=AsyncMock())
    return adapter


def _message(text, *, chat_id=-100123, thread_id=1):
    return SimpleNamespace(
        text=text,
        message_id=42,
        message_thread_id=thread_id,
        is_topic_message=thread_id is not None,
        chat=SimpleNamespace(
            id=chat_id,
            type="supergroup",
            is_forum=True,
        ),
    )


@pytest.mark.asyncio
async def test_scoped_literal_trigger_replies_and_consumes():
    adapter = _adapter()

    handled = await adapter._maybe_handle_literal_trigger_reply(
        _message("@all Here is the announcement")
    )

    assert handled is True
    adapter._bot.send_message.assert_awaited_once()
    kwargs = adapter._bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == -100123
    assert kwargs["message_thread_id"] == 1
    assert kwargs["reply_to_message_id"] == 42
    assert kwargs["text"] == ROSTER


@pytest.mark.asyncio
async def test_general_forum_topic_normalizes_missing_thread_id_to_one():
    adapter = _adapter()

    handled = await adapter._maybe_handle_literal_trigger_reply(
        _message("@all General topic announcement", thread_id=None)
    )

    assert handled is True
    kwargs = adapter._bot.send_message.await_args.kwargs
    assert kwargs["reply_to_message_id"] == 42
    assert "message_thread_id" not in kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "chat_id", "thread_id"),
    [
        ("ordinary message", -100123, 1),
        ("@all wrong chat", -100999, 1),
        ("@all wrong topic", -100123, 2),
        ("email@all.example", -100123, 1),
    ],
)
async def test_literal_trigger_does_not_escape_scope(text, chat_id, thread_id):
    adapter = _adapter()

    handled = await adapter._maybe_handle_literal_trigger_reply(
        _message(text, chat_id=chat_id, thread_id=thread_id)
    )

    assert handled is False
    adapter._bot.send_message.assert_not_awaited()