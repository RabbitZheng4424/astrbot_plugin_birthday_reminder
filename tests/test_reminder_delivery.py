from __future__ import annotations

from dataclasses import dataclass

import pytest

from astrbot_plugin_birthday_reminder.main import BirthdayReminderPlugin


@dataclass
class DueReminder:
    message: str


class FakeService:
    def __init__(self):
        self.state = {}

    def get_runtime_state(self):
        return dict(self.state)

    def save_runtime_state(self, state):
        self.state = dict(state)

    def collect_due_reminders(self, today=None):
        return [DueReminder("生日提醒")]


class FakeContext:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def send_message(self, session, chain):
        self.calls.append((session, chain))
        return self.result


@pytest.mark.asyncio
async def test_failed_delivery_stays_pending():
    plugin = BirthdayReminderPlugin.__new__(BirthdayReminderPlugin)
    plugin.config = {
        "birthday_proactive_enabled": True,
        "birthday_proactive_session": "test:FriendMessage:user",
    }
    plugin.birthday_service = FakeService()
    plugin.context = FakeContext(False)

    sent = await plugin._run_reminders_if_due(force=True)

    assert sent is False
    assert "birthday_last_sent_date" not in plugin.birthday_service.state
    assert plugin.birthday_service.state["birthday_pending_date"]


@pytest.mark.asyncio
async def test_successful_delivery_is_recorded():
    plugin = BirthdayReminderPlugin.__new__(BirthdayReminderPlugin)
    plugin.config = {
        "birthday_proactive_enabled": True,
        "birthday_proactive_session": "test:FriendMessage:user",
    }
    plugin.birthday_service = FakeService()
    plugin.context = FakeContext(True)

    sent = await plugin._run_reminders_if_due(force=True)

    assert sent is True
    assert plugin.birthday_service.state["birthday_last_sent_date"]
    assert "birthday_pending_date" not in plugin.birthday_service.state


def test_invalid_reminder_time_uses_default():
    plugin = BirthdayReminderPlugin.__new__(BirthdayReminderPlugin)
    plugin.config = {"birthday_proactive_time": "25:99"}

    assert plugin._parse_reminder_time() == (8, 0)


def test_session_normalization_preserves_colons_in_session_id():
    plugin = BirthdayReminderPlugin.__new__(BirthdayReminderPlugin)

    result = plugin._normalize_proactive_session_umo("test:私聊:user:thread")

    assert result == "test:FriendMessage:user:thread"
