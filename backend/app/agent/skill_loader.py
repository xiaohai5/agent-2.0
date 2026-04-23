from __future__ import annotations

from pathlib import Path

from .models import ModuleName, SkillMetadata, SkillReference


MODULE_REFERENCE_FILES: dict[ModuleName, tuple[str, str]] = {
    "travel_planning": ("travel_planning.md", "旅游规划"),
    "ticket_service": ("ticket_service.md", "票务服务"),
    "hotel_restaurant": ("hotel_restaurant.md", "酒店与餐厅推荐"),
    "rag": ("rag.md", "RAG 问答"),
    "general_chat": ("general_chat.md", "其他通用聊天"),
}


def load_skill_metadata(skill_path: str | Path) -> SkillMetadata:
    path = Path(skill_path)
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    name = "travel-life-service-auto-router"
    description = ""

    if lines[:1] == ["---"]:
        frontmatter: list[str] = []
        for line in lines[1:]:
            if line == "---":
                break
            frontmatter.append(line)
        for line in frontmatter:
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip()

    references: dict[ModuleName, SkillReference] = {}
    reference_dir = path.parent / "references"
    for module, (filename, title) in MODULE_REFERENCE_FILES.items():
        ref_path = reference_dir / filename
        references[module] = SkillReference(module=module, path=str(ref_path), title=title)

    return SkillMetadata(
        name=name,
        description=description,
        path=str(path),
        references=references,
    )


def read_reference(reference: SkillReference) -> str:
    return Path(reference.path).read_text(encoding="utf-8")

