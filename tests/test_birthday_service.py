from __future__ import annotations

import json
from datetime import date

from astrbot_plugin_birthday_reminder.models import BirthdayEntry
from astrbot_plugin_birthday_reminder.services.birthday_service import BirthdayService
from astrbot_plugin_birthday_reminder.services.natural_language_service import (
    BirthdayNaturalLanguageService,
)
from astrbot_plugin_birthday_reminder.services.storage_service import BirthdayStorage


class MemoryStorage:
    def __init__(self):
        self.birthdays = []
        self.state = {}

    def load_birthdays(self):
        return self.birthdays

    def save_birthdays(self, items):
        self.birthdays = items

    def load_runtime_state(self):
        return dict(self.state)

    def save_runtime_state(self, state):
        self.state = dict(state)


def make_service(config=None):
    storage = MemoryStorage()
    return BirthdayService(config or {}, storage=storage), storage


def test_add_solar_and_lunar_birthdays():
    service, storage = make_service()

    solar_result = service.add_birthday("雨林；生日：10月22日；历法：阳历")
    lunar_result = service.add_birthday_from_fields(
        name="天涯",
        birthday_text="八月十五",
        calendar_type="lunar_nong",
        aliases=["涯涯"],
    )

    assert "已添加 雨林" in solar_result
    assert "已添加 天涯（农）" in lunar_result
    assert len(storage.birthdays) == 2
    lunar = service.find_entry("涯涯")
    assert lunar is not None
    assert lunar.calendar_type == "lunar_nong"
    assert lunar.next_birthday_solar


def test_invalid_dates_are_rejected():
    service, storage = make_service()

    assert "没能识别" in service.add_birthday("测试；生日：13月40日")
    assert "没能识别" in service.add_birthday("测试；生日：2001年2月29日")
    assert storage.birthdays == []


def test_leap_day_resolves_to_the_next_leap_year():
    service, _ = make_service()
    entry = BirthdayEntry(id="1", name="闰日", birth_month=2, birth_day=29)

    assert service._resolve_next_birthday(entry, date(2025, 3, 1)) == date(2028, 2, 29)


def test_bad_template_falls_back_to_default():
    service, _ = make_service({"birthday_template": "{unknown}"})
    entry = BirthdayEntry(id="1", name="雨林", birth_month=10, birth_day=22)

    message = service._render_message(entry, 7, date(2026, 10, 22))

    assert "雨林" in message
    assert "7 天" in message


def test_natural_language_intents():
    parser = BirthdayNaturalLanguageService()

    add = parser.parse("帮我添加雨林的生日是10月22日")
    lookup = parser.parse("天涯的生日是几月几日")
    delete = parser.parse("删除雨林的生日")

    assert add and add.intent == "birthday_add"
    assert lookup and lookup.intent == "birthday_lookup" and lookup.payload == "天涯"
    assert delete and delete.intent == "birthday_delete" and delete.payload == "雨林"


def test_corrupt_storage_is_backed_up(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "astrbot_plugin_birthday_reminder.services.storage_service.get_astrbot_data_path",
        lambda: str(tmp_path),
    )
    storage = BirthdayStorage()
    storage.birthdays_path.write_text("{broken", encoding="utf-8")

    assert storage.load_birthdays() == []
    assert not storage.birthdays_path.exists()
    assert list(storage.root.glob("birthdays.corrupt_*.json"))


def test_storage_write_is_valid_json(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "astrbot_plugin_birthday_reminder.services.storage_service.get_astrbot_data_path",
        lambda: str(tmp_path),
    )
    storage = BirthdayStorage()

    storage.save_birthdays([{"name": "雨林"}])

    assert json.loads(storage.birthdays_path.read_text(encoding="utf-8")) == [
        {"name": "雨林"}
    ]
    assert not storage.birthdays_path.with_suffix(".json.tmp").exists()
