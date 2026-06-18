from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class BirthdayEntry:
    id: str
    name: str
    birth_month: int
    birth_day: int
    calendar_type: str = "solar"
    birth_year: int | None = None
    aliases: list[str] = field(default_factory=list)
    note: str = ""
    next_birthday_solar: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def display_name(self) -> str:
        if self.calendar_type == "lunar_yin":
            return f"{self.name}（阴）"
        if self.calendar_type == "lunar_nong":
            return f"{self.name}（农）"
        return self.name

    @property
    def calendar_label(self) -> str:
        if self.calendar_type == "lunar_yin":
            return "（阴）"
        if self.calendar_type == "lunar_nong":
            return "（农）"
        return ""

    @property
    def is_lunar(self) -> bool:
        return self.calendar_type in {"lunar_yin", "lunar_nong"}


@dataclass(slots=True)
class BirthdayReminder:
    entry: BirthdayEntry
    remind_date: datetime
    days_before: int
    target_birthday: str
    message: str
