from __future__ import annotations

import re
from pathlib import Path

from .schemas import MemoryBlock, MemoryUpdate


DEFAULT_MEMORY_FILES: dict[str, str] = {
    "CLAUDE.md": """# Agent Long-Term Memory

@user_profile.md
@project_context.md
@decisions.md
@tasks.md
@coding_style.md
@safety.md
""",
    "user_profile.md": """# User Profile

## Preferences

## Question Style

## Workflow Preferences
""",
    "project_context.md": """# Project Context

## Overview

## Tech Stack

## Core Modules

## Important Paths
""",
    "decisions.md": """# Decisions

## Confirmed Decisions

## Rejected Options

## Rationale
""",
    "tasks.md": """# Tasks

## Current Goals

## Pending Items

## Later
""",
    "coding_style.md": """# Coding Style

## Preferences

## Conventions

## Avoid
""",
    "safety.md": """# Safety

## Sensitive Information

## Forbidden Actions

## Confirmation Required
""",
}


class LongTermMemoryStore:
    def __init__(self, memory_dir: str | Path | None = None) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self.memory_dir = Path(memory_dir) if memory_dir else repo_root / "memory"

    def ensure_files(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in DEFAULT_MEMORY_FILES.items():
            path = self.memory_dir / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    def listed_files(self) -> list[Path]:
        self.ensure_files()
        index = self.memory_dir / "CLAUDE.md"
        content = index.read_text(encoding="utf-8")
        refs = re.findall(r"@([A-Za-z0-9_.\-/]+\.md)", content)
        files = [self.memory_dir / ref for ref in refs]
        return [path for path in files if path.exists()]

    def load_blocks(self) -> list[MemoryBlock]:
        blocks: list[MemoryBlock] = []
        for path in self.listed_files():
            blocks.extend(self._split_markdown(path))
        return blocks

    def apply_update(self, update: MemoryUpdate) -> bool:
        if update.action != "append" or not update.content.strip():
            return False

        self.ensure_files()
        path = self.memory_dir / update.file
        if path.parent != self.memory_dir or path.suffix.lower() != ".md":
            return False
        if not path.exists():
            return False

        text = path.read_text(encoding="utf-8")
        bullet = f"- {update.content.strip()}"
        if bullet in text:
            return False

        pattern = re.compile(rf"(^##\s+{re.escape(update.section)}\s*$)", re.MULTILINE)
        match = pattern.search(text)
        if not match:
            text = text.rstrip() + f"\n\n## {update.section}\n\n{bullet}\n"
        else:
            insert_at = self._section_end(text, match.end())
            prefix = text[:insert_at].rstrip()
            suffix = text[insert_at:]
            text = f"{prefix}\n{bullet}\n{suffix.lstrip()}"

        path.write_text(text, encoding="utf-8")
        return True

    def _split_markdown(self, path: Path) -> list[MemoryBlock]:
        text = path.read_text(encoding="utf-8")
        current_section = path.stem
        current_lines: list[str] = []
        blocks: list[MemoryBlock] = []

        for line in text.splitlines():
            heading = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
            if heading:
                self._flush_block(blocks, path.name, current_section, current_lines)
                current_section = heading.group(2).strip()
                current_lines = []
                continue
            current_lines.append(line)

        self._flush_block(blocks, path.name, current_section, current_lines)
        return blocks

    @staticmethod
    def _flush_block(blocks: list[MemoryBlock], filename: str, section: str, lines: list[str]) -> None:
        content = "\n".join(lines).strip()
        if content:
            blocks.append(MemoryBlock(file=filename, section=section, content=content))

    @staticmethod
    def _section_end(text: str, start: int) -> int:
        match = re.search(r"^##\s+", text[start:], re.MULTILINE)
        return len(text) if not match else start + match.start()

