from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

from lunardate import LunarDate

from ..models import BirthdayEntry, BirthdayReminder
from .storage_service import BirthdayStorage

SOLAR_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m-%d",
    "%m/%d",
    "%m.%d",
)

CHINESE_MONTH_MAP = {
    "正": 1,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "冬": 11,
    "十一": 11,
    "腊": 12,
    "十二": 12,
}

CHINESE_DAY_MAP = {
    "初一": 1,
    "初二": 2,
    "初三": 3,
    "初四": 4,
    "初五": 5,
    "初六": 6,
    "初七": 7,
    "初八": 8,
    "初九": 9,
    "初十": 10,
    "十一": 11,
    "十二": 12,
    "十三": 13,
    "十四": 14,
    "十五": 15,
    "十六": 16,
    "十七": 17,
    "十八": 18,
    "十九": 19,
    "二十": 20,
    "廿一": 21,
    "廿二": 22,
    "廿三": 23,
    "廿四": 24,
    "廿五": 25,
    "廿六": 26,
    "廿七": 27,
    "廿八": 28,
    "廿九": 29,
    "三十": 30,
}


class BirthdayService:
    def __init__(self, config: dict | None = None, storage: BirthdayStorage | None = None):
        self.config = config or {}
        self.storage = storage or BirthdayStorage()

    def list_entries(self, refresh: bool = True) -> list[BirthdayEntry]:
        entries = [BirthdayEntry(**item) for item in self.storage.load_birthdays()]
        if refresh:
            entries = self._refresh_entries(entries)
        entries.sort(key=lambda item: (item.birth_month, item.birth_day, item.name.lower()))
        return entries

    def list_entries_for_page(self) -> list[dict[str, Any]]:
        today = date.today()
        items: list[dict[str, Any]] = []
        for entry in self.list_entries(refresh=True):
            next_date = self._parse_iso_date(entry.next_birthday_solar)
            days_left = (next_date - today).days if next_date else None
            items.append(
                {
                    "id": entry.id,
                    "name": entry.name,
                    "display_name": entry.display_name,
                    "aliases": entry.aliases,
                    "note": entry.note,
                    "calendar_type": entry.calendar_type,
                    "birth_year": entry.birth_year,
                    "birth_month": entry.birth_month,
                    "birth_day": entry.birth_day,
                    "original_birthday": self._format_original_birthday(entry),
                    "next_birthday_solar": entry.next_birthday_solar,
                    "days_left": days_left,
                }
            )
        return items

    def build_birthday_list_text(self) -> str:
        entries = self.list_entries(refresh=True)
        if not entries:
            return "生日列表还是空的。"
        lines = ["生日列表（按 1 月到 12 月排序）："]
        current_month = None
        for entry in entries:
            if current_month != entry.birth_month:
                current_month = entry.birth_month
                lines.append(f"\n{current_month} 月")
            lines.append(
                f"- {entry.display_name}：{self._format_original_birthday(entry)}"
                f" -> 下次公历 {entry.next_birthday_solar or '未计算'}"
            )
        return "\n".join(lines)

    def build_upcoming_text(self, days: int = 30) -> str:
        today = date.today()
        items = []
        for entry in self.list_entries(refresh=True):
            next_date = self._parse_iso_date(entry.next_birthday_solar)
            if next_date is None:
                continue
            delta = (next_date - today).days
            if 0 <= delta <= days:
                items.append((next_date, f"- {entry.display_name}：{next_date.isoformat()}（还有 {delta} 天）"))
        if not items:
            return f"未来 {days} 天内没有生日。"
        items.sort(key=lambda item: item[0])
        return f"未来 {days} 天生日：\n" + "\n".join(line for _, line in items)

    def get_birthday_text(self, query: str) -> str:
        entry = self.find_entry(query)
        if entry is None:
            return f"没有在生日列表里找到“{query}”。"
        next_date = self._parse_iso_date(entry.next_birthday_solar)
        if next_date is None:
            return f"找到了 {entry.display_name}，但下一次公历生日还没算出来。"
        delta = (next_date - date.today()).days
        if delta == 0:
            return f"{entry.display_name} 的生日是今天，对应公历日期是 {next_date.isoformat()}。"
        return (
            f"{entry.display_name} 的生日是 {self._format_original_birthday(entry)}，"
            f"下一次公历生日是 {next_date.isoformat()}，还有 {delta} 天。"
        )

    def add_birthday(self, payload: str) -> str:
        parsed = self._parse_add_payload(payload)
        if not parsed:
            return (
                "添加失败。可以这样写：\n"
                "- /birthday add 雨林；生日：10月22日；历法：阳历\n"
                "- 帮我添加天涯的生日是农历八月十五"
            )
        name = parsed["name"]
        entry = self._build_entry(
            name=name,
            birthday_text=parsed["birthday_text"],
            calendar_hint=parsed.get("calendar_type", ""),
            aliases=parsed.get("aliases", []),
            note=parsed.get("note", ""),
        )
        if entry is None:
            return "没能识别生日日期，请用 10月22日、2001-10-22、农历八月十五 这类格式再说一次。"

        entries = self.list_entries(refresh=False)
        matched = self._match_entry(entries, name)
        now_text = datetime.now().isoformat(timespec="seconds")
        if matched:
            entry.id = matched.id
            entry.created_at = matched.created_at
            action = "已更新"
            entries = [item for item in entries if item.id != matched.id]
        else:
            entry.created_at = now_text
            action = "已添加"
        entry.updated_at = now_text
        entries.append(entry)
        entries = self._refresh_entries(entries)
        self._save_entries(entries)
        return (
            f"{action} {entry.display_name} 的生日：{self._format_original_birthday(entry)}，"
            f"下一次公历生日是 {entry.next_birthday_solar or '未计算'}。"
        )

    def add_birthday_from_fields(
        self,
        *,
        name: str,
        birthday_text: str,
        calendar_type: str = "",
        aliases: list[str] | None = None,
        note: str = "",
    ) -> str:
        segments = [name.strip(), f"生日：{birthday_text.strip()}"]
        if calendar_type:
            segments.append(f"历法：{calendar_type.strip()}")
        if aliases:
            segments.append("别名：" + ", ".join(item.strip() for item in aliases if item.strip()))
        if note:
            segments.append(f"备注：{note.strip()}")
        return self.add_birthday("；".join(segments))

    def delete_birthday(self, query: str) -> str:
        entries = self.list_entries(refresh=False)
        matched = self._match_entry(entries, query)
        if matched is None:
            return f"没有找到“{query}”对应的生日记录。"
        entries = [item for item in entries if item.id != matched.id]
        self._save_entries(entries)
        return f"已删除 {matched.display_name} 的生日记录。"

    def delete_birthday_by_id(self, entry_id: str) -> bool:
        entries = self.list_entries(refresh=False)
        remaining = [item for item in entries if item.id != entry_id]
        if len(remaining) == len(entries):
            return False
        self._save_entries(remaining)
        return True

    def find_entry(self, query: str) -> BirthdayEntry | None:
        return self._match_entry(self.list_entries(refresh=True), query)

    def refresh_cached_next_birthdays(self) -> int:
        entries = self.list_entries(refresh=False)
        before_map = {item.id: item.next_birthday_solar for item in entries}
        refreshed = self._refresh_entries(entries)
        changed = sum(1 for item in refreshed if before_map.get(item.id) != item.next_birthday_solar)
        self._save_entries(refreshed)
        return changed

    def collect_due_reminders(self, today: date | None = None) -> list[BirthdayReminder]:
        today = today or date.today()
        offsets = self._get_offsets()
        reminders: list[BirthdayReminder] = []
        for entry in self.list_entries(refresh=True):
            next_date = self._parse_iso_date(entry.next_birthday_solar)
            if next_date is None:
                continue
            days = (next_date - today).days
            if days not in offsets:
                continue
            reminders.append(
                BirthdayReminder(
                    entry=entry,
                    remind_date=datetime.combine(today, datetime.min.time()),
                    days_before=days,
                    target_birthday=next_date.isoformat(),
                    message=self._render_message(entry, days, next_date),
                )
            )
        reminders.sort(key=lambda item: (item.days_before, item.entry.birth_month, item.entry.birth_day))
        return reminders

    def get_runtime_state(self) -> dict[str, Any]:
        return self.storage.load_runtime_state()

    def save_runtime_state(self, state: dict[str, Any]) -> None:
        self.storage.save_runtime_state(state)

    def _save_entries(self, entries: list[BirthdayEntry]) -> None:
        self.storage.save_birthdays([asdict(item) for item in entries])

    def _refresh_entries(self, entries: list[BirthdayEntry]) -> list[BirthdayEntry]:
        today = date.today()
        changed = False
        refreshed: list[BirthdayEntry] = []
        for entry in entries:
            resolved = self._resolve_next_birthday(entry, today)
            iso_text = resolved.isoformat() if resolved else ""
            if entry.next_birthday_solar != iso_text:
                entry.next_birthday_solar = iso_text
                entry.updated_at = datetime.now().isoformat(timespec="seconds")
                changed = True
            refreshed.append(entry)
        if changed:
            self._save_entries(refreshed)
        return refreshed

    def _resolve_next_birthday(self, entry: BirthdayEntry, today: date) -> date | None:
        if entry.is_lunar:
            current = self._resolve_lunar_birthday(today.year, entry.birth_month, entry.birth_day)
            if current is None:
                return None
            if today > current + timedelta(days=1):
                return self._resolve_lunar_birthday(today.year + 1, entry.birth_month, entry.birth_day)
            if today <= current:
                return current
            return self._resolve_lunar_birthday(today.year + 1, entry.birth_month, entry.birth_day)
        try:
            current = date(today.year, entry.birth_month, entry.birth_day)
            return current if current >= today else date(today.year + 1, entry.birth_month, entry.birth_day)
        except ValueError:
            return None

    def _resolve_lunar_birthday(self, year: int, month: int, day: int) -> date | None:
        try:
            return LunarDate(year, month, day).toSolarDate()
        except Exception:
            return None

    def _render_message(self, entry: BirthdayEntry, days_before: int, target_birthday: date) -> str:
        if days_before == 0:
            template = str(
                self.config.get(
                    "birthday_today_template",
                    "今天是 {name}{calendar_label} 的生日，对应公历日期是 {birthday}。",
                )
            )
            return template.format(
                name=entry.name,
                birthday=target_birthday.isoformat(),
                calendar_label=entry.calendar_label,
            )
        template = str(
            self.config.get(
                "birthday_template",
                "提醒一下，{name}{calendar_label} 还有 {days} 天过生日，对应公历日期是 {birthday}。",
            )
        )
        return template.format(
            name=entry.name,
            days=days_before,
            birthday=target_birthday.isoformat(),
            calendar_label=entry.calendar_label,
        )

    def _get_offsets(self) -> list[int]:
        raw = self.config.get("birthday_remind_offsets", [7, 1, 0])
        if not isinstance(raw, list):
            raw = [raw]
        offsets: list[int] = []
        for item in raw:
            try:
                offsets.append(int(item))
            except (TypeError, ValueError):
                continue
        return sorted(set(offsets), reverse=True) or [7, 1, 0]

    def _match_entry(self, entries: list[BirthdayEntry], query: str) -> BirthdayEntry | None:
        normalized_query = self._normalize_lookup_text(query)
        if not normalized_query:
            return None
        exact = None
        fuzzy = None
        for entry in entries:
            candidates = [entry.name, entry.display_name, *entry.aliases]
            normalized_candidates = {
                self._normalize_lookup_text(item)
                for item in candidates
                if self._normalize_lookup_text(item)
            }
            if normalized_query in normalized_candidates:
                exact = entry
                break
            if any(normalized_query in item or item in normalized_query for item in normalized_candidates):
                fuzzy = fuzzy or entry
        return exact or fuzzy

    def _normalize_lookup_text(self, text: str) -> str:
        normalized = str(text or "").strip().lower()
        normalized = normalized.replace("（阴）", "").replace("（农）", "")
        normalized = normalized.replace("生日", "")
        normalized = re.sub(r"[，,。！？!?:：\s]+", "", normalized)
        return normalized

    def _parse_add_payload(self, payload: str) -> dict[str, Any] | None:
        data: dict[str, Any] = {}
        text = payload.strip()
        parts = [item.strip() for item in re.split(r"[；;]", text) if item.strip()]
        for index, part in enumerate(parts):
            if (":" not in part) and ("：" not in part):
                if index == 0 and "name" not in data:
                    data["name"] = part
                continue
            key, value = re.split(r"[:：]", part, maxsplit=1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"名字", "名称", "name"}:
                data["name"] = value
            elif key in {"生日", "birthday"}:
                data["birthday_text"] = value
            elif key in {"历法", "类型", "calendar", "calendar_type"}:
                data["calendar_type"] = value
            elif key in {"别名", "aliases", "alias"}:
                data["aliases"] = [item.strip() for item in re.split(r"[，,、]", value) if item.strip()]
            elif key in {"备注", "note"}:
                data["note"] = value

        if data.get("name") and data.get("birthday_text"):
            return data

        natural_patterns = (
            r"^(?:添加|新增|加入|记下)?(?P<name>.+?)的生日(?:是|为)?(?P<birthday>.+)$",
            r"^(?:把)?(?P<name>.+?)(?:的)?生日(?:记到|加到)?(?:生日列表)?(?:里|中)?(?:，|,)?(?:生日是|生日为|是)?(?P<birthday>.+)$",
        )
        for pattern in natural_patterns:
            match = re.match(pattern, text)
            if not match:
                continue
            name = match.group("name").strip().strip("，,。！？!?:： ")
            birthday = match.group("birthday").strip().strip("，,。！？!?:： ")
            if name and birthday:
                return {"name": name, "birthday_text": birthday}
        return None

    def _build_entry(
        self,
        *,
        name: str,
        birthday_text: str,
        calendar_hint: str = "",
        aliases: list[str] | None = None,
        note: str = "",
    ) -> BirthdayEntry | None:
        parsed = self._parse_birthday_text(birthday_text, calendar_hint=calendar_hint)
        if parsed is None:
            return None
        now_text = datetime.now().isoformat(timespec="seconds")
        return BirthdayEntry(
            id=uuid.uuid4().hex,
            name=name.strip(),
            birth_year=parsed.get("birth_year"),
            birth_month=parsed["birth_month"],
            birth_day=parsed["birth_day"],
            calendar_type=parsed["calendar_type"],
            aliases=aliases or [],
            note=note.strip(),
            next_birthday_solar="",
            created_at=now_text,
            updated_at=now_text,
        )

    def _parse_birthday_text(self, text: str, calendar_hint: str = "") -> dict[str, Any] | None:
        raw = (text or "").strip()
        if not raw:
            return None
        calendar_type = self._normalize_calendar_type(calendar_hint or raw)
        cleaned = raw
        cleaned = cleaned.replace("阳历", "").replace("公历", "")
        cleaned = cleaned.replace("农历", "").replace("阴历", "")
        cleaned = cleaned.replace("生日是", "").replace("生日为", "")
        cleaned = cleaned.strip().strip("，,。！？!?:： ")

        if calendar_type == "solar":
            full_year_match = re.match(r"^(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日$", cleaned)
            if full_year_match:
                return {
                    "birth_year": int(full_year_match.group("year")),
                    "birth_month": int(full_year_match.group("month")),
                    "birth_day": int(full_year_match.group("day")),
                    "calendar_type": "solar",
                }
            month_day_match = re.match(r"^(?P<month>\d{1,2})月(?P<day>\d{1,2})日$", cleaned)
            if month_day_match:
                return {
                    "birth_year": None,
                    "birth_month": int(month_day_match.group("month")),
                    "birth_day": int(month_day_match.group("day")),
                    "calendar_type": "solar",
                }
            for fmt in SOLAR_DATE_PATTERNS:
                try:
                    parsed = datetime.strptime(cleaned, fmt)
                except ValueError:
                    continue
                return {
                    "birth_year": parsed.year if "%Y" in fmt else None,
                    "birth_month": parsed.month,
                    "birth_day": parsed.day,
                    "calendar_type": "solar",
                }
            return None

        lunar_match = re.match(
            r"^(?P<month>[正冬腊一二三四五六七八九十0-9]{1,3})月(?P<day>[初十廿卅一二三四五六七八九0-9]{1,3})$",
            cleaned,
        )
        if lunar_match is None:
            lunar_match = re.match(r"^(?P<month>\d{1,2})[-/.](?P<day>\d{1,2})$", cleaned)
        if lunar_match is None:
            return None

        month = self._parse_lunar_number(lunar_match.group("month"), is_day=False)
        day = self._parse_lunar_number(lunar_match.group("day"), is_day=True)
        if month is None or day is None:
            return None
        return {
            "birth_year": None,
            "birth_month": month,
            "birth_day": day,
            "calendar_type": calendar_type,
        }

    def _normalize_calendar_type(self, text: str) -> str:
        lowered = str(text or "").lower()
        if "阴历" in lowered:
            return "lunar_yin"
        if "农历" in lowered:
            return "lunar_nong"
        return "solar"

    def _parse_lunar_number(self, token: str, *, is_day: bool) -> int | None:
        token = str(token or "").strip()
        if token.isdigit():
            value = int(token)
            if 1 <= value <= (30 if is_day else 12):
                return value
            return None
        if is_day:
            return CHINESE_DAY_MAP.get(token)
        return CHINESE_MONTH_MAP.get(token)

    def _format_original_birthday(self, entry: BirthdayEntry) -> str:
        prefix = ""
        if entry.calendar_type == "lunar_yin":
            prefix = "阴历"
        elif entry.calendar_type == "lunar_nong":
            prefix = "农历"
        if entry.birth_year:
            return f"{prefix}{entry.birth_year:04d}-{entry.birth_month:02d}-{entry.birth_day:02d}"
        if prefix:
            return f"{prefix}{entry.birth_month}月{entry.birth_day}日"
        return f"{entry.birth_month}月{entry.birth_day}日"

    def _parse_iso_date(self, raw: str) -> date | None:
        text = str(raw or "").strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
