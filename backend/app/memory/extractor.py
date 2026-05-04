from __future__ import annotations

import re

from .schemas import MemoryUpdate


SENSITIVE_PATTERNS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passwd",
    "pwd",
    "密钥",
    "密码",
    "令牌",
)


class LongTermMemoryExtractor:
    def extract(self, user_message: str, assistant_message: str) -> list[MemoryUpdate]:
        text = user_message.strip()
        if not text or self._has_sensitive_text(text):
            return []

        updates: list[MemoryUpdate] = []

        if self._contains(text, ("以后", "以后都", "每次", "默认", "我希望", "我喜欢", "偏好")):
            updates.append(MemoryUpdate("append", "user_profile.md", "Workflow Preferences", text))

        if self._contains(text, ("项目", "技术栈", "架构", "接口", "目录", "数据库", "后端", "前端")):
            updates.append(MemoryUpdate("append", "project_context.md", "Overview", text))

        if self._contains(text, ("决定", "确认", "就按", "采用", "不要用", "不用", "方案")):
            updates.append(MemoryUpdate("append", "decisions.md", "Confirmed Decisions", text))

        if self._contains(text, ("目标", "待办", "下一步", "计划", "任务", "先做")):
            updates.append(MemoryUpdate("append", "tasks.md", "Current Goals", text))

        if self._contains(text, ("代码风格", "命名", "测试", "实现", "不要过度", "简化版")):
            updates.append(MemoryUpdate("append", "coding_style.md", "Preferences", text))

        if self._contains(text, ("不要", "禁止", "不能", "需要确认", "敏感", "安全")):
            updates.append(MemoryUpdate("append", "safety.md", "Confirmation Required", text))

        return self._dedupe(updates)

    @staticmethod
    def _contains(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _has_sensitive_text(text: str) -> bool:
        lowered = text.lower()
        if any(pattern in lowered for pattern in SENSITIVE_PATTERNS):
            return True
        return bool(re.search(r"sk-[A-Za-z0-9_-]{16,}", text))

    @staticmethod
    def _dedupe(updates: list[MemoryUpdate]) -> list[MemoryUpdate]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[MemoryUpdate] = []
        for update in updates:
            key = (update.file, update.section, update.content)
            if key not in seen:
                seen.add(key)
                unique.append(update)
        return unique

