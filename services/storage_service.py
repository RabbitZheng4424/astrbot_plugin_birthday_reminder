from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
except ImportError:  # pragma: no cover
    def get_astrbot_data_path() -> str:
        return str(Path.cwd() / "data")


PLUGIN_NAME = "astrbot_plugin_birthday_reminder"


class BirthdayStorage:
    def __init__(self, plugin_name: str = PLUGIN_NAME):
        self.plugin_name = plugin_name
        self.root = Path(get_astrbot_data_path()) / "plugin_data" / plugin_name
        self.root.mkdir(parents=True, exist_ok=True)
        self.birthdays_path = self.root / "birthdays.json"
        self.runtime_path = self.root / "runtime_state.json"

    def load_birthdays(self) -> list[dict[str, Any]]:
        if not self.birthdays_path.exists():
            return []
        try:
            data = json.loads(self.birthdays_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def save_birthdays(self, items: list[dict[str, Any]]) -> None:
        self.birthdays_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_runtime_state(self) -> dict[str, Any]:
        if not self.runtime_path.exists():
            return {}
        try:
            data = json.loads(self.runtime_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def save_runtime_state(self, state: dict[str, Any]) -> None:
        self.runtime_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
