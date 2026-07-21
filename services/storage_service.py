from __future__ import annotations

import json
import os
from datetime import datetime
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
        data = self._load_json(self.birthdays_path, [])
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def save_birthdays(self, items: list[dict[str, Any]]) -> None:
        self._write_json(self.birthdays_path, items)

    def load_runtime_state(self) -> dict[str, Any]:
        data = self._load_json(self.runtime_path, {})
        return data if isinstance(data, dict) else {}

    def save_runtime_state(self, state: dict[str, Any]) -> None:
        self._write_json(self.runtime_path, state)

    def _load_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            self._backup_corrupt_file(path)
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        try:
            temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _backup_corrupt_file(self, path: Path) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f"{path.stem}.corrupt_{timestamp}{path.suffix}")
        try:
            path.replace(backup_path)
        except OSError:
            pass
