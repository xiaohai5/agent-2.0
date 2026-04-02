import io
import json
import os
import tempfile
from pathlib import Path

from langchain_core.documents import Document

try:
    from . import config_data as config
except ImportError:
    import config_data as config

"""
鏂囨。鍔犺浇妯″潡锛氬皢涓婁紶鏂囦欢杞崲涓?LangChain Document 鍒楄〃銆?
褰撳墠瀹炵幇浣跨敤 Docling 瑙ｆ瀽鏂囨。锛屽苟閫氳繃 HybridChunker 杈撳嚭鍙洿鎺ュ叆搴撶殑鍒嗗潡缁撴灉銆?
"""


def _resolve_export_type():
    """Allow env override while defaulting to a non-chunked Docling export mode."""
    try:
        from langchain_docling.loader import ExportType
    except ImportError as exc:
        raise ImportError(
            "Docling import failed. Ensure `langchain-docling`, `docling`, "
            "`docling-core`, and compatible transitive dependencies are installed. "
            f"Original error: {exc}"
        ) from exc

    export_type_name = os.getenv("DOCLING_EXPORT_TYPE", "markdown").strip().upper()
    if hasattr(ExportType, export_type_name):
        return getattr(ExportType, export_type_name)

    valid_values = ", ".join(name for name in dir(ExportType) if name.isupper())
    raise ValueError(
        f"Unsupported DOCLING_EXPORT_TYPE={export_type_name!r}. Valid values: {valid_values}"
    )


_SUFFIX_ALIASES = {
    ".tx": ".txt",
    ".htm": ".html",
}
_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_PLAIN_TEXT_SUFFIXES = {".txt", ".json"}
_TEXT_DOC_TYPE = "text"
_MARKDOWN_DOC_TYPE = "markdown"
_TABLE_DOC_TYPE = "table"
_STRUCTURED_DOC_TYPE = "structured"


def _normalize_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.strip().lower()
    if not suffix:
        return ".tmp"
    return _SUFFIX_ALIASES.get(suffix, suffix)


def _build_temp_path(filename: str, suffix: str) -> tuple[str, str]:
    temp_dir = tempfile.mkdtemp()
    safe_stem = Path(filename).stem.strip() or "upload"
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in safe_stem)
    safe_stem = safe_stem[:80] or "upload"
    temp_path = str(Path(temp_dir) / f"{safe_stem}{suffix}")
    return temp_dir, temp_path


def _write_temp_upload(uploaded_file) -> tuple[str, str]:
    filename = getattr(uploaded_file, "name", "upload")
    suffix = _normalize_suffix(filename)
    file_bytes = uploaded_file.getvalue()

    if suffix.lower() == ".xls":
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "Legacy `.xls` support requires `pandas` to be installed. "
                f"Original error: {exc}"
            ) from exc

        try:
            workbook = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, engine="xlrd")
        except ImportError as exc:
            raise ImportError(
                "Legacy `.xls` support requires `xlrd` to be installed. "
                f"Original error: {exc}"
            ) from exc

        temp_dir, temp_path = _build_temp_path(filename, ".xlsx")
        try:
            with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
                for sheet_name, frame in workbook.items():
                    safe_name = str(sheet_name)[:31] or "Sheet1"
                    frame.to_excel(writer, sheet_name=safe_name, index=False)
            return temp_path, temp_dir
        except Exception:
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
            raise

    temp_dir, temp_path = _build_temp_path(filename, suffix)
    with open(temp_path, "wb") as tmp:
        tmp.write(file_bytes)
    return temp_path, temp_dir


def _base_metadata(filename: str, **extra: object) -> dict[str, object]:
    metadata: dict[str, object] = {"source": filename}
    metadata.update(extra)
    return metadata


def _load_plain_text_document(uploaded_file, *, doc_type: str = "text") -> list[Document]:
    filename = getattr(uploaded_file, "name", "upload")
    raw_bytes = uploaded_file.getvalue()
    text = raw_bytes.decode("utf-8", errors="ignore")
    return [
        Document(
            page_content=text,
            metadata=_base_metadata(filename, doc_type=doc_type),
        )
    ]


def _normalize_cell_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and str(value).lower() == "nan":
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _dataframe_to_table_document(
    frame,
    *,
    filename: str,
    sheet_name: str | None = None,
) -> Document | None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "Table parsing requires `pandas` to be installed. "
            f"Original error: {exc}"
        ) from exc

    normalized = frame.copy()
    normalized = normalized.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if normalized.empty:
        return None

    normalized.columns = [
        _normalize_cell_value(column) or f"column_{index + 1}"
        for index, column in enumerate(normalized.columns)
    ]
    normalized = normalized.fillna("")

    headers = [str(column).strip() or f"column_{index + 1}" for index, column in enumerate(normalized.columns)]
    rows: list[dict[str, str]] = []
    preview_lines: list[str] = []

    for row_index, row in enumerate(normalized.itertuples(index=False, name=None), start=1):
        row_payload = {
            headers[column_index]: _normalize_cell_value(value)
            for column_index, value in enumerate(row)
        }
        if not any(row_payload.values()):
            continue
        rows.append(row_payload)
        if len(preview_lines) < 5:
            rendered_cells = [f"{key}: {value}" for key, value in row_payload.items() if value]
            preview_lines.append(f"row {row_index}: " + "; ".join(rendered_cells))

    if not rows:
        return None

    title = filename if not sheet_name else f"{filename} / {sheet_name}"
    preview = [
        f"table document: {title}",
        f"columns: {', '.join(headers)}",
        *preview_lines,
    ]
    return Document(
        page_content="\n".join(preview),
        metadata=_base_metadata(
            filename,
            doc_type=_TABLE_DOC_TYPE,
            table_headers=headers,
            table_rows=rows,
            row_count=len(rows),
            sheet_name=sheet_name or "",
        ),
    )


def _load_csv_documents(uploaded_file) -> list[Document]:
    filename = getattr(uploaded_file, "name", "upload")
    raw_bytes = uploaded_file.getvalue()

    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "CSV parsing requires `pandas` to be installed. "
            f"Original error: {exc}"
        ) from exc

    frame = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            frame = pd.read_csv(io.BytesIO(raw_bytes), dtype=str, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except Exception:
            frame = None
            break

    if frame is None:
        return _load_plain_text_document(uploaded_file, doc_type=_TEXT_DOC_TYPE)

    table_doc = _dataframe_to_table_document(frame, filename=filename)
    if table_doc is None:
        return _load_plain_text_document(uploaded_file, doc_type=_TEXT_DOC_TYPE)
    return [table_doc]


def _load_excel_documents(uploaded_file) -> list[Document]:
    filename = getattr(uploaded_file, "name", "upload")
    suffix = _normalize_suffix(filename)
    raw_bytes = uploaded_file.getvalue()

    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "Excel parsing requires `pandas` to be installed. "
            f"Original error: {exc}"
        ) from exc

    engine = "xlrd" if suffix == ".xls" else None
    workbook = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=None, dtype=str, engine=engine)

    documents: list[Document] = []
    for sheet_name, frame in workbook.items():
        table_doc = _dataframe_to_table_document(frame, filename=filename, sheet_name=str(sheet_name))
        if table_doc is not None:
            documents.append(table_doc)
    return documents


def _load_jsonl_documents(uploaded_file) -> list[Document]:
    filename = getattr(uploaded_file, "name", "upload")
    raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    documents: list[Document] = []

    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"Invalid JSONL at line {line_number}: each line must be a JSON object")

        text = str(payload.get("text", "")).strip()
        if not text:
            text = str(payload.get("content", "")).strip()
        if not text:
            title = str(payload.get("title", "")).strip()
            if title:
                text = title
        if not text:
            continue

        metadata = payload.get("metadata", {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError(f"Invalid JSONL at line {line_number}: metadata must be an object")

        merged_metadata = dict(metadata)
        merged_metadata.setdefault("source", filename)
        if payload.get("doc_id") is not None:
            merged_metadata.setdefault("doc_id", payload.get("doc_id"))
        if payload.get("title") is not None:
            merged_metadata.setdefault("title", payload.get("title"))
        if payload.get("category") is not None:
            merged_metadata.setdefault("category", payload.get("category"))
        if payload.get("tags") is not None:
            merged_metadata.setdefault("tags", payload.get("tags"))

        for key, value in payload.items():
            if key in {"text", "content", "metadata"}:
                continue
            merged_metadata.setdefault(key, value)

        documents.append(
            Document(
                page_content=text,
                metadata={
                    **merged_metadata,
                    "doc_type": _TEXT_DOC_TYPE,
                },
            )
        )

    return documents


def load_file_to_document(uploaded_file):
    """
    鏍规嵁涓婁紶鍚庣殑鏂囦欢瀵硅薄鍔犺浇涓?Document 鍒楄〃銆?
    鍏煎 Streamlit 鐨?UploadedFile锛屼互鍙婇」鐩唴鑷畾涔夌殑 _MemoryUploadFile銆?
    """
    filename = getattr(uploaded_file, "name", "upload")
    suffix = _normalize_suffix(filename)

    if suffix == ".jsonl":
        return _load_jsonl_documents(uploaded_file)

    if suffix in _MARKDOWN_SUFFIXES:
        return _load_plain_text_document(uploaded_file, doc_type=_MARKDOWN_DOC_TYPE)

    if suffix == ".csv":
        return _load_csv_documents(uploaded_file)

    if suffix in {".xls", ".xlsx"}:
        return _load_excel_documents(uploaded_file)

    if suffix in _PLAIN_TEXT_SUFFIXES:
        return _load_plain_text_document(uploaded_file, doc_type=_TEXT_DOC_TYPE)

    try:
        from langchain_docling import DoclingLoader
    except ImportError as exc:
        raise ImportError(
            "Docling import failed. Ensure `langchain-docling`, `docling`, "
            "`docling-core`, and compatible transitive dependencies are installed. "
            f"Original error: {exc}"
        ) from exc

    export_type = _resolve_export_type()
    tmp_path, tmp_dir = _write_temp_upload(uploaded_file)

    try:
        loader = DoclingLoader(
            file_path=tmp_path,
            export_type=export_type,
        )
        docs = loader.load()
        doc_type = _MARKDOWN_DOC_TYPE if str(export_type).lower().endswith("markdown") else _STRUCTURED_DOC_TYPE
        for doc in docs:
            metadata = dict(doc.metadata or {})
            metadata.setdefault("source", filename)
            metadata.setdefault("doc_type", doc_type)
            doc.metadata = metadata
        return docs
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


if __name__ == "__main__":
    pass
