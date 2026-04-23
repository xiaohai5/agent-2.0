"""Document-type-aware chunking strategies for ingestion."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from project_config import SplitterConfig
except ImportError:
    from project_config import SplitterConfig


MARKDOWN_DOC_TYPES = {"markdown"}
TABLE_DOC_TYPES = {"table"}
STRUCTURED_DOC_TYPES = {"structured"}
TEXT_DOC_TYPES = {"text"}
_TEMP_TABLE_METADATA_KEYS = {"table_rows", "table_headers"}


def default_text_separators() -> list[str]:
    return [
        "\n\n",
        "\n",
        "\u3002",
        "\uff01",
        "\uff1f",
        "\uff1b",
        ". ",
        "! ",
        "? ",
        "; ",
        "\uff0c",
        ", ",
        " ",
        "",
    ]


def default_markdown_separators() -> list[str]:
    return [
        "\n## ",
        "\n# ",
        "\n### ",
        "\n#### ",
        "\n##### ",
        "\n###### ",
        "\n\n",
        "\n",
        "\u3002",
        "\uff01",
        "\uff1f",
        "\uff1b",
        ". ",
        "! ",
        "? ",
        "; ",
        "\uff0c",
        ", ",
        " ",
        "",
    ]


def default_structured_separators() -> list[str]:
    return [
        "\n# ",
        "\n## ",
        "\n### ",
        "\n\n",
        "\n",
        "\n\u8868",
        "\n\u56fe",
        "\u3002",
        "\uff01",
        "\uff1f",
        "\uff1b",
        ". ",
        "! ",
        "? ",
        "; ",
        "\uff0c",
        ", ",
        " ",
        "",
    ]


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key not in _TEMP_TABLE_METADATA_KEYS}


def _build_recursive_splitter(config: SplitterConfig, separators: list[str]) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=separators,
    )


def _clone_with_content(doc: Document, content: str, extra_metadata: dict[str, Any] | None = None) -> Document:
    metadata = dict(doc.metadata or {})
    metadata.update(extra_metadata or {})
    return Document(page_content=content, metadata=metadata)


def _split_markdown_sections(doc: Document) -> list[Document]:
    text = (doc.page_content or "").strip()
    if not text:
        return []

    lines = text.splitlines()
    sections: list[Document] = []
    current_lines: list[str] = []
    current_title = str((doc.metadata or {}).get("title") or "").strip()
    current_level = 0

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match:
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append(
                        _clone_with_content(
                            doc,
                            content,
                            {
                                "section_title": current_title,
                                "section_level": current_level,
                            },
                        )
                    )
            current_lines = [line]
            current_title = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            continue
        current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append(
                _clone_with_content(
                    doc,
                    content,
                    {
                        "section_title": current_title,
                        "section_level": current_level,
                    },
                )
            )
    return sections or [doc]


def _split_structured_sections(doc: Document) -> list[Document]:
    text = (doc.page_content or "").strip()
    if not text:
        return []

    numbered_heading_chars = "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341"
    chunks = re.split(
        rf"(?=^\s*(?:#{{1,6}}\s+.+|(?:\d+(?:\.\d+)*|[{numbered_heading_chars}]+)[\u3001.\s]+\S+))",
        text,
        flags=re.MULTILINE,
    )

    sections: list[Document] = []
    for block in chunks:
        content = block.strip()
        if not content:
            continue
        first_line = content.splitlines()[0].strip()
        sections.append(_clone_with_content(doc, content, {"section_title": first_line[:120]}))
    return sections or [doc]


def _render_table_row(headers: list[str], row: dict[str, Any], row_number: int) -> str:
    cells: list[str] = []
    for header in headers:
        value = str(row.get(header, "")).strip()
        if not value:
            continue
        cells.append(f"{header}: {value}")
    body = "; ".join(cells) if cells else "(empty row)"
    return f"row {row_number}: {body}"


def _chunk_table_document(doc: Document, config: SplitterConfig) -> list[Document]:
    metadata = dict(doc.metadata or {})
    headers = [str(item).strip() for item in metadata.get("table_headers", []) if str(item).strip()]
    rows = metadata.get("table_rows", [])
    if not isinstance(rows, list) or not rows:
        sanitized = _sanitize_metadata(metadata)
        sanitized.setdefault("chunk_type", "table_summary")
        return [Document(page_content=doc.page_content, metadata=sanitized)]

    batch_size = max(1, config.table_row_batch_size)
    overlap = min(config.table_row_overlap, batch_size - 1) if batch_size > 1 else 0
    step = max(1, batch_size - overlap)
    sanitized = _sanitize_metadata(metadata)
    sheet_name = str(sanitized.get("sheet_name", "")).strip()
    source_name = str(sanitized.get("filename") or sanitized.get("source") or "").strip()
    header_text = ", ".join(headers) if headers else "(no headers)"
    doc_title = source_name if not sheet_name else f"{source_name} / {sheet_name}"

    chunks: list[Document] = []
    chunks.append(
        Document(
            page_content="\n".join(
                [
                    f"table document: {doc_title}",
                    f"columns: {header_text}",
                    f"rows: {len(rows)}",
                ]
            ),
            metadata={
                **sanitized,
                "chunk_type": "table_summary",
                "row_start": 1,
                "row_end": len(rows),
            },
        )
    )

    for start_index in range(0, len(rows), step):
        batch = rows[start_index : start_index + batch_size]
        if not batch:
            continue

        row_lines = [
            _render_table_row(headers, row, start_index + offset + 1)
            for offset, row in enumerate(batch)
            if isinstance(row, dict)
        ]
        if not row_lines:
            continue

        chunks.append(
            Document(
                page_content="\n".join(
                    [
                        f"table document: {doc_title}",
                        f"columns: {header_text}",
                        *row_lines,
                    ]
                ),
                metadata={
                    **sanitized,
                    "chunk_type": "table_rows",
                    "row_start": start_index + 1,
                    "row_end": start_index + len(batch),
                    "row_count": len(batch),
                },
            )
        )

    return chunks


def chunk_documents(docs: list[Document], config: SplitterConfig) -> list[Document]:
    text_splitter = _build_recursive_splitter(config, default_text_separators())
    markdown_splitter = _build_recursive_splitter(config, default_markdown_separators())
    structured_splitter = _build_recursive_splitter(config, default_structured_separators())
    chunked_docs: list[Document] = []

    for doc in docs:
        metadata = dict(doc.metadata or {})
        doc_type = str(metadata.get("doc_type", "text")).strip().lower()

        if doc_type in TABLE_DOC_TYPES:
            chunked_docs.extend(_chunk_table_document(doc, config))
            continue

        if doc_type in MARKDOWN_DOC_TYPES:
            section_docs = _split_markdown_sections(doc)
            split_docs = markdown_splitter.split_documents(section_docs)
            chunked_docs.extend(split_docs or section_docs)
            continue

        if doc_type in STRUCTURED_DOC_TYPES:
            section_docs = _split_structured_sections(doc)
            split_docs = structured_splitter.split_documents(section_docs)
            chunked_docs.extend(split_docs or section_docs)
            continue

        if doc_type not in TEXT_DOC_TYPES:
            metadata["doc_type"] = "text"
            doc.metadata = metadata
        split_docs = text_splitter.split_documents([doc])
        chunked_docs.extend(split_docs or [doc])

    for index, chunk in enumerate(chunked_docs):
        metadata = dict(chunk.metadata or {})
        metadata["chunk_index"] = index
        metadata.setdefault("doc_type", "text")
        chunk.metadata = metadata

    return chunked_docs
