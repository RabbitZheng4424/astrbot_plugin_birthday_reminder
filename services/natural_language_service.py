from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class NaturalLanguageIntent:
    intent: str
    payload: str = ""


class BirthdayNaturalLanguageService:
    AT_TAG_PREFIX_PATTERN = re.compile(r"^(?:\s*\[At:[^\]]+\]\s*)+")
    LEADING_MENTION_PATTERN = re.compile(r"^(?:\s*@\S+\s*)+")

    ADD_PATTERNS = (
        r"^(?:帮我)?(?:添加|新增|加入|记下)(?P<payload>.+?的生日.+)$",
        r"^(?:帮我)?把(?P<payload>.+?生日.+?)(?:记到|加到)(?:生日列表)?$",
        r"^(?:帮我)?(?:添加|新增|加入)(?P<payload>.+?)(?:到)?生日列表$",
    )
    DELETE_PATTERNS = (
        r"^(?:帮我)?(?:删除|删掉|移除)(?P<payload>.+?)(?:的)?生日(?:记录)?$",
        r"^(?:帮我)?把(?P<payload>.+?)从生日列表(?:里|中)?删掉$",
        r"^(?:帮我)?从生日列表(?:里|中)?删除(?P<payload>.+)$",
    )
    LIST_PATTERNS = (
        r"^(?:看看|查看|列出|显示)(?:生日列表|所有生日)$",
        r"^(?:我)?(?:有哪些|有谁)生日$",
    )
    LOOKUP_PATTERNS = (
        r"^(?:帮我)?(?:(?:查一下|查查|看看|看一下|告诉我))?(?P<payload>.+?)(?:的)?生日(?:是)?(?:几月几日|多少号|哪天|日期|什么时候)?(?:，?(?:查一下|查查|看一下))?\??$",
        r"^(?:帮我)?查(?P<payload>.+?)生日\??$",
    )

    def parse(self, message: str) -> NaturalLanguageIntent | None:
        text = self._normalize_message(message)
        if not text or text.startswith("/"):
            return None

        for pattern in self.ADD_PATTERNS:
            if match := re.match(pattern, text, re.IGNORECASE):
                payload = self._normalize_payload(match.groupdict().get("payload", ""))
                if payload:
                    return NaturalLanguageIntent("birthday_add", payload)

        for pattern in self.DELETE_PATTERNS:
            if match := re.match(pattern, text, re.IGNORECASE):
                payload = self._normalize_payload(match.groupdict().get("payload", ""))
                if payload:
                    return NaturalLanguageIntent("birthday_delete", payload)

        for pattern in self.LIST_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return NaturalLanguageIntent("birthday_list", "")

        for pattern in self.LOOKUP_PATTERNS:
            if match := re.match(pattern, text, re.IGNORECASE):
                payload = self._normalize_payload(match.groupdict().get("payload", ""))
                if payload:
                    return NaturalLanguageIntent("birthday_lookup", payload)
        return None

    def _normalize_payload(self, payload: str) -> str:
        return payload.strip().strip("，,。！？!?:： ")

    def _normalize_message(self, message: str) -> str:
        text = (message or "").strip()
        text = self.AT_TAG_PREFIX_PATTERN.sub("", text)
        text = self.LEADING_MENTION_PATTERN.sub("", text)
        return text.strip()
