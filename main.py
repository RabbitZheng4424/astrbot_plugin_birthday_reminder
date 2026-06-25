from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

from quart import jsonify, request

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register

from .services.birthday_service import BirthdayService
from .services.natural_language_service import BirthdayNaturalLanguageService

PLUGIN_NAME = "astrbot_plugin_birthday_reminder"


def _load_plugin_version() -> str:
    metadata_path = Path(__file__).with_name("metadata.yaml")
    try:
        content = metadata_path.read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    match = re.search(r"^version:\s*([^\r\n]+)\s*$", content, re.MULTILINE)
    if not match:
        return "unknown"
    return match.group(1).strip().strip("\"'")


PLUGIN_VERSION = _load_plugin_version()


@register(
    PLUGIN_NAME,
    "瑞贝特",
    "独立管理生日列表，支持自然语言增删、农历生日和定时主动提醒的 AstrBot 插件",
    PLUGIN_VERSION,
)
class BirthdayReminderPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.birthday_service = BirthdayService(self.config)
        self.nl_service = BirthdayNaturalLanguageService()
        self._birthday_task: asyncio.Task | None = None
        self._register_page_apis(context)

    async def initialize(self):
        logger.info("[BirthdayReminder] 插件已启动。")
        self._start_birthday_task()

    async def terminate(self):
        if self._birthday_task and not self._birthday_task.done():
            self._birthday_task.cancel()
            try:
                await self._birthday_task
            except asyncio.CancelledError:
                pass
        self._birthday_task = None

    def _register_page_apis(self, context: Context) -> None:
        context.register_web_api(
            f"/{PLUGIN_NAME}/birthdays",
            self.page_birthdays,
            ["GET"],
            "List birthdays",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/birthdays/add",
            self.page_birthdays_add,
            ["POST"],
            "Add birthday",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/birthdays/delete",
            self.page_birthdays_delete,
            ["POST"],
            "Delete birthday",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/birthdays/refresh",
            self.page_birthdays_refresh,
            ["POST"],
            "Refresh next solar birthdays",
        )

    async def _page_response(self, payload: dict, status: int = 200):
        response = jsonify(payload)
        response.status_code = status
        return response

    async def _page_error(self, message: str, status_code: int = 400):
        return await self._page_response({"ok": False, "message": message}, status_code)

    async def _page_json_body(self) -> dict:
        try:
            data = await request.get_json(silent=True)
        except TypeError:
            data = await request.get_json()
        return data if isinstance(data, dict) else {}

    async def page_birthdays(self):
        return await self._page_response(
            {
                "ok": True,
                "pluginVersion": PLUGIN_VERSION,
                "items": self.birthday_service.list_entries_for_page(),
            }
        )

    async def page_birthdays_add(self):
        payload = await self._page_json_body()
        if payload.get("text"):
            message = self.birthday_service.add_birthday(str(payload.get("text", "")))
            return await self._page_response({"ok": True, "message": message})
        name = str(payload.get("name", "")).strip()
        birthday_text = str(payload.get("birthday", "")).strip()
        if not name or not birthday_text:
            return await self._page_error("name and birthday are required", 400)
        aliases = payload.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        message = self.birthday_service.add_birthday_from_fields(
            name=name,
            birthday_text=birthday_text,
            calendar_type=str(payload.get("calendar_type", "")).strip(),
            aliases=[str(item).strip() for item in aliases if str(item).strip()],
            note=str(payload.get("note", "")).strip(),
        )
        return await self._page_response({"ok": True, "message": message})

    async def page_birthdays_delete(self):
        payload = await self._page_json_body()
        entry_id = str(payload.get("id", "")).strip()
        if entry_id:
            ok = self.birthday_service.delete_birthday_by_id(entry_id)
            if not ok:
                return await self._page_error("birthday not found", 404)
            return await self._page_response({"ok": True, "message": "已删除生日记录。"})
        query = str(payload.get("query", "")).strip()
        if not query:
            return await self._page_error("id or query is required", 400)
        return await self._page_response(
            {"ok": True, "message": self.birthday_service.delete_birthday(query)}
        )

    async def page_birthdays_refresh(self):
        changed = self.birthday_service.refresh_cached_next_birthdays()
        return await self._page_response(
            {"ok": True, "message": f"已刷新生日映射，共更新 {changed} 条记录。"}
        )

    def _start_birthday_task(self) -> None:
        if self._birthday_task and not self._birthday_task.done():
            return
        self._birthday_task = asyncio.create_task(
            self._birthday_loop(),
            name="birthday_reminder_loop",
        )

    async def _birthday_loop(self) -> None:
        while True:
            try:
                await self._run_reminders_if_due()
                await asyncio.sleep(self._seconds_until_next_check())
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover
                logger.warning("[BirthdayReminder] 后台提醒循环异常: %s", exc)
                await asyncio.sleep(60)

    async def _run_reminders_if_due(self, force: bool = False) -> bool:
        if not bool(self.config.get("birthday_proactive_enabled", True)):
            return False

        state = self.birthday_service.get_runtime_state()
        now = datetime.now()
        today_text = now.date().isoformat()
        hour, minute = self._parse_reminder_time()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if not force and now < target_time and state.get("birthday_pending_date") != today_text:
            return False

        due_reminders = self.birthday_service.collect_due_reminders(today=now.date())
        if not due_reminders:
            state["birthday_last_checked_date"] = today_text
            state.pop("birthday_pending_date", None)
            self.birthday_service.save_runtime_state(state)
            return False

        if not force and state.get("birthday_last_sent_date") == today_text:
            return False

        target_session = self._resolve_target_session(state)
        if not target_session:
            state["birthday_pending_date"] = today_text
            self.birthday_service.save_runtime_state(state)
            logger.info("[BirthdayReminder] 今日生日提醒待补发：尚未记录管理员会话。")
            return False

        lines = [item.message for item in due_reminders]
        try:
            await self.context.send_message(target_session, MessageChain().message("\n".join(lines)))
        except Exception as exc:  # pragma: no cover
            state["birthday_pending_date"] = today_text
            self.birthday_service.save_runtime_state(state)
            logger.warning("[BirthdayReminder] 主动发送生日提醒失败: %s", exc)
            return False

        state["birthday_last_sent_date"] = today_text
        state["birthday_last_checked_date"] = today_text
        state.pop("birthday_pending_date", None)
        self.birthday_service.save_runtime_state(state)
        logger.info("[BirthdayReminder] 已发送今日生日提醒到 %s", target_session)
        return True

    def _seconds_until_next_check(self) -> float:
        now = datetime.now()
        hour, minute = self._parse_reminder_time()
        next_check = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        state = self.birthday_service.get_runtime_state()
        today_text = now.date().isoformat()
        if now >= next_check:
            if state.get("birthday_pending_date") == today_text and state.get("birthday_last_sent_date") != today_text:
                return 300.0
            next_check = next_check + timedelta(days=1)
        delta = (next_check - now).total_seconds()
        return max(delta, 60.0)

    def _parse_reminder_time(self) -> tuple[int, int]:
        raw = str(self.config.get("birthday_proactive_time", "08:00")).strip()
        match = re.match(r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})$", raw)
        if not match:
            return 8, 0
        hour = max(0, min(23, int(match.group("hour"))))
        minute = max(0, min(59, int(match.group("minute"))))
        return hour, minute

    def _resolve_target_session(self, state: dict) -> str:
        explicit = str(self.config.get("birthday_proactive_session", "")).strip()
        if explicit:
            return explicit
        return str(state.get("latest_admin_umo", "")).strip()

    def _deny_if_not_admin(self, event: AstrMessageEvent) -> str | None:
        if not bool(self.config.get("admin_only_operations", True)):
            return None
        return None if event.is_admin() else "这个插件当前只允许管理员操作。"

    def _extract_subcommand_payload(self, message: str, command_name: str) -> str:
        text = (message or "").strip()
        pattern = rf"^/?{re.escape(command_name)}\s*(?P<payload>.*)$"
        match = re.match(pattern, text, re.IGNORECASE)
        if not match:
            return ""
        return match.group("payload").strip()

    @filter.command_group("birthday")
    def birthday(self):
        pass

    @birthday.command("list")
    async def birthday_list(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        yield event.plain_result(self.birthday_service.build_birthday_list_text())

    @birthday.command("upcoming")
    async def birthday_upcoming(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        yield event.plain_result(self.birthday_service.build_upcoming_text(days=30))

    @birthday.command("show")
    async def birthday_show(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        payload = self._extract_subcommand_payload(event.message_str, "birthday show")
        if not payload:
            yield event.plain_result("用法：/birthday show 名字")
            return
        yield event.plain_result(self.birthday_service.get_birthday_text(payload))

    @birthday.command("add")
    async def birthday_add(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        payload = self._extract_subcommand_payload(event.message_str, "birthday add")
        if not payload:
            yield event.plain_result(
                "用法：/birthday add 雨林；生日：10月22日；历法：阳历；别名：小雨；备注：朋友"
            )
            return
        yield event.plain_result(self.birthday_service.add_birthday(payload))

    @birthday.command("delete")
    async def birthday_delete(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        payload = self._extract_subcommand_payload(event.message_str, "birthday delete")
        if not payload:
            yield event.plain_result("用法：/birthday delete 名字")
            return
        yield event.plain_result(self.birthday_service.delete_birthday(payload))

    @birthday.command("refresh")
    async def birthday_refresh(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        changed = self.birthday_service.refresh_cached_next_birthdays()
        yield event.plain_result(f"已刷新生日映射，共更新 {changed} 条记录。")

    @birthday.command("remind-now")
    async def birthday_remind_now(self, event: AstrMessageEvent):
        denied = self._deny_if_not_admin(event)
        if denied:
            yield event.plain_result(denied)
            return
        sent = await self._run_reminders_if_due(force=True)
        if sent:
            yield event.plain_result("已尝试发送今天应触发的生日提醒。")
            return
        due = self.birthday_service.collect_due_reminders()
        if not due:
            yield event.plain_result("今天没有需要发送的生日提醒。")
            return
        yield event.plain_result("今天有提醒，但暂时没有可用目标会话，请先让管理员和机器人说一句话。")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def remember_latest_admin_session(self, event: AstrMessageEvent):
        if not event.is_admin():
            return
        umo = str(getattr(event, "unified_msg_origin", "") or "").strip()
        if not umo:
            return
        state = self.birthday_service.get_runtime_state()
        if state.get("latest_admin_umo") != umo:
            state["latest_admin_umo"] = umo
            self.birthday_service.save_runtime_state(state)
        if state.get("birthday_pending_date") == datetime.now().date().isoformat():
            asyncio.create_task(self._run_reminders_if_due(force=True))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_natural_language_message(self, event: AstrMessageEvent):
        if not bool(self.config.get("enable_natural_language_commands", True)):
            return
        intent = self.nl_service.parse(event.message_str or "")
        if intent is None:
            return
        denied = self._deny_if_not_admin(event)
        if denied:
            return

        if intent.intent == "birthday_add":
            yield event.plain_result(self.birthday_service.add_birthday(intent.payload))
            event.stop_event()
            return
        if intent.intent == "birthday_delete":
            yield event.plain_result(self.birthday_service.delete_birthday(intent.payload))
            event.stop_event()
            return
        if intent.intent == "birthday_list":
            yield event.plain_result(self.birthday_service.build_birthday_list_text())
            event.stop_event()
            return
        if intent.intent == "birthday_lookup":
            yield event.plain_result(self.birthday_service.get_birthday_text(intent.payload))
            event.stop_event()

