import base64
import re
import time
from typing import Any

import requests
import streamlit as st

from services.api_client import api_client
from utils.session import ensure_session_defaults, logout_user


VIEW_LABEL_TO_KEY = {
    "知识库管理": "vector_store",
    "出行对话": "chat",
}
VIEW_KEY_TO_LABEL = {value: key for key, value in VIEW_LABEL_TO_KEY.items()}

st.set_page_config(page_title="出行小助手", page_icon="🧳", layout="centered")
ensure_session_defaults()


def _on_view_change() -> None:
    selected_label = st.session_state.get("nav_view_label", "知识库管理")
    st.session_state["active_view"] = VIEW_LABEL_TO_KEY.get(selected_label, "vector_store")


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    pending_confirmation = message.get("pending_confirmation")
    final_summary = message.get("final_summary")

    normalized_metadata = dict(metadata)
    if isinstance(pending_confirmation, dict) and pending_confirmation and "pending_confirmation" not in normalized_metadata:
        normalized_metadata["pending_confirmation"] = pending_confirmation
    if isinstance(final_summary, dict) and final_summary and "final_summary" not in normalized_metadata:
        normalized_metadata["final_summary"] = final_summary

    normalized = {
        "role": str(message.get("role", "assistant")).strip() or "assistant",
        "content": str(message.get("content", "")).strip(),
        "metadata": normalized_metadata,
    }
    status = str(message.get("status", "")).strip()
    if status:
        normalized["status"] = status
    if isinstance(pending_confirmation, dict) and pending_confirmation:
        normalized["pending_confirmation"] = pending_confirmation
    if isinstance(final_summary, dict) and final_summary:
        normalized["final_summary"] = final_summary
    return normalized


def _normalize_history(history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in history or []:
        if isinstance(item, dict):
            normalized.append(_normalize_message(item))
    return normalized


def _submit_chat(question: str, history: list[dict[str, object]], *, show_spinner: bool = True) -> dict[str, object]:
    top_k = int(st.session_state.get("top_k", 3))

    def run_request() -> dict[str, object]:
        result = api_client.chat(question=question, top_k=top_k, history=_normalize_history(history))
        if isinstance(result, dict):
            result["history"] = _normalize_history(result.get("history"))
        return result

    if show_spinner:
        with st.spinner("正在生成回答..."):
            return run_request()
    return run_request()


def _submit_chat_stream(question: str, history: list[dict[str, object]]):
    top_k = int(st.session_state.get("top_k", 3))
    return api_client.chat_stream(question=question, top_k=top_k, history=_normalize_history(history))

@st.cache_data(show_spinner=False, ttl=3600)
def _load_image_source(image_url: str) -> bytes | str | None:
    normalized = str(image_url).strip()
    if not normalized:
        return None

    if normalized.startswith("data:image/"):
        try:
            _, encoded = normalized.split(",", 1)
            return base64.b64decode(encoded)
        except Exception:
            return None

    if normalized.startswith(("http://", "https://")):
        try:
            response = requests.get(
                normalized,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Referer": normalized,
                },
            )
            response.raise_for_status()
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if content_type.startswith("image/") and response.content:
                return response.content
        except Exception:
            return normalized
        return normalized

    return normalized


def _get_final_summary(message: dict[str, object]) -> dict[str, object]:
    metadata = message.get("metadata")
    if isinstance(metadata, dict):
        final_summary = metadata.get("final_summary")
        if isinstance(final_summary, dict):
            return final_summary
    final_summary = message.get("final_summary")
    return final_summary if isinstance(final_summary, dict) else {}


def _get_pending_confirmation(message: dict[str, object]) -> dict[str, object]:
    metadata = message.get("metadata")
    if isinstance(metadata, dict):
        pending_confirmation = metadata.get("pending_confirmation")
        if isinstance(pending_confirmation, dict):
            return pending_confirmation
    pending_confirmation = message.get("pending_confirmation")
    return pending_confirmation if isinstance(pending_confirmation, dict) else {}


def _extract_image_urls_from_text(text: str) -> list[str]:
    if not text:
        return []

    candidates = re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text, flags=re.IGNORECASE)
    candidates.extend(re.findall(r"https?://[^\s<>\])，。；;,]+", text, flags=re.IGNORECASE))

    image_urls: list[str] = []
    image_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
    for url in candidates:
        normalized = str(url).strip().rstrip(").,;]）。，；")
        lowered = normalized.lower()
        if lowered.endswith(image_suffixes) or any(
            token in lowered for token in ("image", "img", "photo", "picture", "staticmap", "snapshot")
        ):
            if normalized not in image_urls:
                image_urls.append(normalized)
    return image_urls


def _get_image_items(message: dict[str, object]) -> list[dict[str, str]]:
    final_summary = _get_final_summary(message)
    plan_state = final_summary.get("plan_state")
    image_items = None
    if isinstance(plan_state, dict):
        plan_state_items = plan_state.get("image_items")
        if isinstance(plan_state_items, list) and plan_state_items:
            image_items = plan_state_items
    if image_items is None:
        image_items = final_summary.get("image_items")
    normalized_items: list[dict[str, str]] = []
    if isinstance(image_items, list):
        for item in image_items:
            if not isinstance(item, dict):
                continue
            image_url = str(item.get("image_url", "")).strip()
            if not image_url:
                continue
            normalized_items.append(
                {
                    "image_url": image_url,
                    "title": str(item.get("title", "")).strip(),
                    "category": str(item.get("category", "")).strip(),
                    "anchor_text": str(item.get("anchor_text", item.get("title", ""))).strip(),
                }
            )
    if normalized_items:
        return normalized_items

    image_urls = final_summary.get("image_urls")
    if not isinstance(image_urls, list):
        content = str(message.get("content", "")).strip() or str(final_summary.get("final_answer", "")).strip()
        image_urls = _extract_image_urls_from_text(content)
    if not image_urls:
        return []
    return [
        {
            "image_url": str(url).strip(),
            "title": f"图片 {index + 1}",
            "category": "",
            "anchor_text": "",
        }
        for index, url in enumerate(image_urls)
        if str(url).strip()
    ]


def _normalize_binding_text(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(text).lower())



def _submit_quick_chat(prompt: str) -> None:
    result = _submit_chat(prompt, st.session_state["chat_history"], show_spinner=False)
    st.session_state["chat_history"] = _normalize_history(result.get("history"))
    st.rerun()


def _iter_image_binding_keys(item: dict[str, str]) -> list[str]:
    raw_keys = [item.get("anchor_text", ""), item.get("title", ""), item.get("category", "")]
    title = str(item.get("title", "")).strip()
    for part in re.split(r"[\\/|,\uff0c\u3001()\uff08\uff09:\uff1a\s-]+", title):
        cleaned = part.strip()
        if len(cleaned) >= 2:
            raw_keys.append(cleaned)
    normalized_keys: list[str] = []
    for key in raw_keys:
        normalized = _normalize_binding_text(key)
        if normalized and normalized not in normalized_keys:
            normalized_keys.append(normalized)
    return normalized_keys


def _score_paragraph_for_image(paragraph: str, normalized_paragraph: str, item: dict[str, str]) -> int:
    image_url = str(item.get("image_url", "")).strip()
    if image_url and image_url in paragraph:
        return 10_000

    generic_keys = {
        _normalize_binding_text("图片"),
        _normalize_binding_text("推荐理由"),
        _normalize_binding_text("理由"),
        _normalize_binding_text("位置"),
        _normalize_binding_text("地址"),
        _normalize_binding_text("交通"),
        _normalize_binding_text("距离"),
        _normalize_binding_text("价格"),
        _normalize_binding_text("营业时间"),
        _normalize_binding_text("建议"),
        _normalize_binding_text("适合"),
        _normalize_binding_text("酒店"),
        _normalize_binding_text("餐厅"),
        _normalize_binding_text("民宿"),
        _normalize_binding_text("景点"),
    }

    best_score = 0
    for key in _iter_image_binding_keys(item):
        if key in generic_keys:
            continue
        if len(key) < 3:
            continue
        if key in normalized_paragraph:
            best_score = max(best_score, len(key))
    return best_score


def _render_single_image_item(item: dict[str, str]) -> None:
    image_url = str(item.get("image_url", "")).strip()
    if not image_url:
        return
    title = str(item.get("title", "")).strip() or "\u56fe\u7247"
    category = str(item.get("category", "")).strip()
    caption = f"{category} | {title}" if category else title
    image_source = _load_image_source(image_url)
    if image_source is None:
        st.caption(f"\u56fe\u7247\u52a0\u8f7d\u5931\u8d25\uff1a{caption}")
        return
    st.image(image_source, caption=caption, use_container_width=True)


def _render_message_images(message: dict[str, object], placed_indexes: set[int] | None = None) -> None:
    image_items = _get_image_items(message)
    if not image_items:
        return
    skipped = placed_indexes or set()
    for item_index, item in enumerate(image_items):
        if item_index in skipped:
            continue
        _render_single_image_item(item)


def _content_explicitly_mentions_images(content: str, image_items: list[dict[str, str]]) -> bool:
    normalized_content = str(content).strip()
    if not normalized_content:
        return False
    if "图片" in normalized_content or "![](" in normalized_content:
        return True
    for item in image_items:
        image_url = str(item.get("image_url", "")).strip()
        if image_url and image_url in normalized_content:
            return True
    return False



def _assign_images_to_paragraphs(paragraphs: list[str], image_items: list[dict[str, str]]) -> dict[int, list[int]]:
    assignments: dict[int, list[int]] = {}
    normalized_paragraphs = [_normalize_binding_text(paragraph) for paragraph in paragraphs]

    for item_index, item in enumerate(image_items):
        best_paragraph_index = -1
        best_score = 0
        for paragraph_index, paragraph in enumerate(paragraphs):
            score = _score_paragraph_for_image(paragraph, normalized_paragraphs[paragraph_index], item)
            if score > best_score:
                best_score = score
                best_paragraph_index = paragraph_index

        if best_paragraph_index >= 0 and best_score > 0:
            assignments.setdefault(best_paragraph_index, []).append(item_index)

    return assignments


def _strip_empty_markdown_images(text: str) -> str:
    if not text:
        return text
    cleaned = re.sub(r"!\[[^\]]*\]\(\s*[\u200b\u200c\u200d\ufeff]*\s*\)", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", cleaned)
    return cleaned.strip()


def _prepare_stream_display_text(text: str) -> str:
    if not text:
        return ""

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    lowered = cleaned.lower()
    open_index = lowered.rfind("<think>")
    close_index = lowered.rfind("</think>")
    if open_index != -1 and open_index > close_index:
        cleaned = cleaned[:open_index]

    cleaned = re.sub(r"<[^>\n]{0,40}$", "", cleaned)
    return _strip_empty_markdown_images(cleaned).rstrip()


def _render_stream_preview(placeholder: Any, text: str, *, is_waiting: bool) -> str:
    preview = _prepare_stream_display_text(text)
    if preview:
        placeholder.markdown(f"{preview}▌" if is_waiting else preview)
    elif is_waiting:
        placeholder.caption("思考中...")
    else:
        placeholder.empty()
    return preview


def _render_assistant_message(message: dict[str, object], index: int) -> None:
    final_summary = _get_final_summary(message)
    content = str(message.get("content", "")).strip() or str(final_summary.get("final_answer", "")).strip()
    content = _strip_empty_markdown_images(content).strip()
    image_items = _get_image_items(message)
    plan_state = final_summary.get("plan_state")
    is_travel_plan_message = isinstance(plan_state, dict) and bool(plan_state.get("image_items"))
    if image_items:
        paragraphs = re.split(r"\n\s*\n", content) if content else []
        placed_indexes: set[int] = set()
        paragraph_assignments = _assign_images_to_paragraphs(paragraphs, image_items) if paragraphs else {}

        for paragraph_index, paragraph in enumerate(paragraphs):
            st.markdown(paragraph)
            for item_index in paragraph_assignments.get(paragraph_index, []):
                _render_single_image_item(image_items[item_index])
                placed_indexes.add(item_index)

        # If nothing was confidently matched, still render the remaining images so the
        # message does not lose them completely.
        if not is_travel_plan_message and (not paragraphs or not placed_indexes or _content_explicitly_mentions_images(content, image_items)):
            _render_message_images(message, placed_indexes=placed_indexes)
    else:
        st.markdown(content)



def _render_confirmation_action(message: dict[str, object], index: int) -> None:
    pending_confirmation = _get_pending_confirmation(message)
    if isinstance(pending_confirmation, dict) and pending_confirmation:
        if st.button("\u7ee7\u7eed\u6267\u884c", key=f"confirm_continue_{index}"):
            try:
                _submit_quick_chat("\u786e\u8ba4")
            except RuntimeError as exc:
                st.error(str(exc))



def render_login_screen() -> None:
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        st.title("出行小助手")
        st.caption("登录后可管理出行知识库，并通过对话获取路线、酒店、景点和票务建议。")

        login_tab, register_tab = st.tabs(["\u767b\u5f55", "\u6ce8\u518c"])

        with login_tab:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("\u7528\u6237\u540d", key="login_username")
                password = st.text_input("\u5bc6\u7801", type="password", key="login_password")
                submit_login = st.form_submit_button("\u767b\u5f55")

        if submit_login:
            try:
                result = api_client.login(username=username, password=password)
                st.session_state["token"] = result["access_token"]
                st.session_state["username"] = result["username"]
                st.session_state["menu_view"] = ""
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

        with register_tab:
            with st.form("register_form", clear_on_submit=False):
                username = st.text_input("\u7528\u6237\u540d", key="register_username")
                email = st.text_input("\u90ae\u7bb1", key="register_email")
                password = st.text_input("\u5bc6\u7801", type="password", key="register_password")
                submit_register = st.form_submit_button("\u6ce8\u518c")

        if submit_register:
            try:
                result = api_client.register(username=username, email=email, password=password)
                st.session_state["token"] = result["access_token"]
                st.session_state["username"] = result["username"]
                st.session_state["menu_view"] = ""
                st.success(result["message"])
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))


def render_sidebar() -> None:
    with st.sidebar:
        st.header("\u5bfc\u822a")
        st.caption(f"\u5f53\u524d\u7528\u6237\uff1a{st.session_state['username']}")

        if "nav_view_label" not in st.session_state:
            st.session_state["nav_view_label"] = VIEW_KEY_TO_LABEL.get(
                st.session_state.get("active_view", "vector_store"),
                "知识库管理",
            )

        st.radio(
            "\u9875\u9762",
            options=list(VIEW_LABEL_TO_KEY.keys()),
            key="nav_view_label",
            on_change=_on_view_change,
        )
        st.session_state["active_view"] = VIEW_LABEL_TO_KEY.get(
            st.session_state.get("nav_view_label", "知识库管理"),
            "vector_store",
        )

        if st.session_state.get("active_view", "vector_store") == "chat":
            with st.expander("\u5927\u6a21\u578b\u53c2\u6570", expanded=False):
                st.slider("Top K", min_value=1, max_value=10, key="top_k")
            if st.button("\u6e05\u7a7a\u5bf9\u8bdd", use_container_width=True):
                st.session_state["chat_history"] = []
                st.success("\u5bf9\u8bdd\u5df2\u6e05\u7a7a")
                st.rerun()


def render_user_menu() -> None:
    left_col, right_col = st.columns([6, 1])
    with left_col:
        st.markdown("<h1 style='text-align: center;'>出行小助手</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align: center; color: #666;'>\u6587\u6863\u8bb0\u5f55\u4e0e\u5927\u6a21\u578b\u68c0\u7d22\u95ee\u7b54</p>",
            unsafe_allow_html=True,
        )
    with right_col:
        with st.popover(st.session_state["username"], use_container_width=True):
            if st.button("\u4e2a\u4eba\u8d44\u6599", use_container_width=True):
                st.session_state["menu_view"] = "profile"
                st.rerun()
            if st.button("\u4fee\u6539\u5bc6\u7801", use_container_width=True):
                st.session_state["menu_view"] = "change_password"
                st.rerun()
            if st.button("\u9000\u51fa\u767b\u5f55", use_container_width=True):
                logout_user()
                st.rerun()


def render_profile_view() -> None:
    if st.button("\u2190 \u8fd4\u56de\u5de5\u4f5c\u53f0"):
        st.session_state["menu_view"] = ""
        st.rerun()

    st.subheader("\u4e2a\u4eba\u8d44\u6599")
    try:
        profile = api_client.get_profile()
        st.session_state["email"] = profile.get("email", st.session_state.get("email", ""))
    except RuntimeError as exc:
        st.error(str(exc))
        profile = {
            "username": st.session_state.get("username", ""),
            "email": st.session_state.get("email", ""),
        }

    st.write(f"\u7528\u6237\u540d\uff1a{profile.get('username', '')}")
    st.write(f"\u90ae\u7bb1\uff1a{profile.get('email', '')}")


def render_change_password_view() -> None:
    if st.button("\u2190 \u8fd4\u56de\u5de5\u4f5c\u53f0"):
        st.session_state["menu_view"] = ""
        st.rerun()

    st.subheader("\u4fee\u6539\u5bc6\u7801")
    with st.form("change_password_form"):
        username = st.text_input("\u7528\u6237\u540d", value=st.session_state.get("username", ""), disabled=True)
        old_password = st.text_input("\u65e7\u5bc6\u7801", type="password")
        new_password = st.text_input("\u65b0\u5bc6\u7801", type="password")
        confirm_password = st.text_input("\u786e\u8ba4\u65b0\u5bc6\u7801", type="password")
        submit_change = st.form_submit_button("\u63d0\u4ea4\u4fee\u6539")

    if submit_change:
        try:
            result = api_client.change_password(
                username=username,
                old_password=old_password,
                new_password=new_password,
                confirm_password=confirm_password,
            )
            st.success(result["message"])
            logout_user()
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))


def render_vector_store_panel() -> None:
    st.markdown("<h3 style='text-align: center;'>\u6587\u6863\u8bb0\u5f55</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; color: #666;'>\u70b9\u51fb\u4e0a\u4f20\u4f1a\u5148\u89e3\u6790\u6587\u6863\uff0c\u518d\u5199\u5165\u5411\u91cf\u5e93\u5e76\u8bb0\u5f55\u3002</p>",
        unsafe_allow_html=True,
    )

    with st.form("upload_form"):
        uploaded_file = st.file_uploader(
            "\u4e0a\u4f20\u6587\u6863",
            type=["txt", "md", "pdf", "docx", "csv", "json", "jsonl", "html", "htm"],
        )
        submit_upload = st.form_submit_button("\u4e0a\u4f20\u5e76\u5904\u7406")

    if submit_upload:
        if uploaded_file is None:
            st.warning("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u6587\u4ef6\u3002")
        else:
            try:
                result = api_client.upload_document(
                    file_name=uploaded_file.name,
                    file_bytes=uploaded_file.getvalue(),
                )
                st.success(result["message"])
            except RuntimeError as exc:
                st.error(str(exc))

    if st.button("\u5237\u65b0\u6587\u6863\u5217\u8868", use_container_width=True):
        try:
            st.session_state["documents"] = api_client.list_documents()
        except RuntimeError as exc:
            st.error(str(exc))

    documents = st.session_state.get("documents", [])
    if documents:
        st.dataframe(documents, use_container_width=True)
    else:
        st.caption("\u6682\u65e0\u6587\u6863\u8bb0\u5f55\u3002")


def render_chat_panel() -> None:
    st.session_state["chat_history"] = _normalize_history(st.session_state.get("chat_history"))
    for index, message in enumerate(st.session_state["chat_history"]):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                _render_assistant_message(message, index)
                _render_confirmation_action(message, index)
            else:
                st.markdown(message["content"])

    prompt = st.chat_input("\u8bf7\u8f93\u5165\u95ee\u9898")
    if prompt:
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                status_placeholder = st.empty()
                placeholder = st.empty()
                final_payload: dict[str, object] | None = None
                streamed_answer = ""
                rendered_preview = ""
                last_rendered_at = 0.0
                last_status_text = ""

                def update_status(text: str) -> None:
                    nonlocal last_status_text
                    normalized = text.strip()
                    if not normalized or normalized == last_status_text:
                        return
                    last_status_text = normalized
                    status_placeholder.caption(f"思考中: {normalized}")

                def flush_stream(*, force: bool = False, is_waiting: bool = True) -> None:
                    nonlocal rendered_preview, last_rendered_at
                    now = time.monotonic()
                    preview = _prepare_stream_display_text(streamed_answer)
                    if not force:
                        if preview == rendered_preview:
                            return
                        if now - last_rendered_at < 0.08 and abs(len(preview) - len(rendered_preview)) < 24:
                            return
                    rendered_preview = _render_stream_preview(placeholder, streamed_answer, is_waiting=is_waiting)
                    last_rendered_at = now

                try:
                    for event in _submit_chat_stream(prompt, st.session_state["chat_history"][:-1]):
                        event_type = str(event.get("type", "")).strip().lower()
                        if event_type == "delta":
                            streamed_answer += str(event.get("content", ""))
                            flush_stream()
                        elif event_type in {"status", "node_start", "node_complete"}:
                            message = str(event.get("message", "")).strip()
                            node = str(event.get("node", "")).strip()
                            if message:
                                update_status(f"{node + ': ' if node else ''}{message}")
                        elif event_type in {"route_start", "route_complete"}:
                            route = str(event.get("route", "")).strip()
                            route_message = "正在执行子任务" if event_type == "route_start" else "子任务执行完成"
                            update_status(f"{route_message}: {route}")
                        elif event_type == "error":
                            raise RuntimeError(str(event.get("detail", "Request failed")))
                        elif event_type == "done":
                            payload = event.get("payload")
                            if isinstance(payload, dict):
                                final_payload = payload
                    flush_stream(force=True)
                except Exception:
                    final_payload = _submit_chat(prompt, st.session_state["chat_history"][:-1], show_spinner=False)

                result = final_payload or _submit_chat(prompt, st.session_state["chat_history"][:-1], show_spinner=False)
                st.session_state["chat_history"] = _normalize_history(result.get("history"))
                latest_message = st.session_state["chat_history"][-1] if st.session_state["chat_history"] else None
                if isinstance(latest_message, dict) and latest_message.get("role") == "assistant":
                    status_placeholder.empty()
                    placeholder.empty()
                    _render_assistant_message(latest_message, len(st.session_state["chat_history"]) - 1)
                    _render_confirmation_action(latest_message, len(st.session_state["chat_history"]) - 1)
                else:
                    status_placeholder.empty()
                    placeholder.markdown(str(result.get("answer", "")))
            except RuntimeError as exc:
                st.error(str(exc))


def _format_plan_field_label(field_name: str) -> str:
    mapping = {
        "origin": "\u51fa\u53d1\u5730",
        "destination": "\u76ee\u7684\u5730",
        "departure_date": "\u51fa\u53d1\u65e5\u671f",
        "return_date": "\u8fd4\u7a0b\u65e5\u671f",
        "travelers": "\u51fa\u884c\u4eba\u6570",
        "budget": "\u9884\u7b97",
        "title": "\u8ba1\u5212\u6807\u9898",
        "route": "\u8ba1\u5212\u7c7b\u578b",
        "plan_summary": "\u884c\u7a0b\u6458\u8981",
        "ticket_option": "\u5df2\u9501\u5b9a\u8f66\u7968",
        "hotel_option": "\u5df2\u9501\u5b9a\u4f4f\u5bbf",
        "plan_version": "\u5df2\u9501\u5b9a\u65b9\u6848",
        "route_option": "\u5df2\u9501\u5b9a\u8def\u7ebf",
        "scenic_option": "\u5df2\u9501\u5b9a\u666f\u70b9",
        "locked_items": "\u5df2\u9501\u5b9a\u9879\u76ee",
    }
    return mapping.get(field_name, field_name.replace('_', ' ').title())


def _format_plan_status(status: str) -> str:
    mapping = {
        "draft": "??",
        "ready_for_confirmation": "待确认",
        "confirmed": "已确认",
        "archived": "已归档",
    }
    normalized = str(status or "").strip().lower()
    return mapping.get(normalized, normalized or "??")


def _format_plan_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return "\u672a\u586b\u5199"
    if isinstance(value, list):
        rendered = [
            _format_plan_value(item)
            for item in value
            if item not in (None, "", [], {})
        ]
        return "\u3001".join(rendered) if rendered else "\u672a\u586b\u5199"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            if item in (None, "", [], {}):
                continue
            parts.append(f"{_format_plan_field_label(str(key))}\uff1a{_format_plan_value(item)}")
        return "\uff1b".join(parts) if parts else "\u672a\u586b\u5199"
    return str(value)


def _render_plan_dict(title: str, payload: dict[str, Any]) -> None:
    st.markdown(f"**{title}**")
    if not isinstance(payload, dict) or not payload:
        st.caption("\u6682\u65e0\u5185\u5bb9\u3002")
        return
    for key, value in payload.items():
        if value in (None, "", [], {}):
            continue
        st.write(f"{_format_plan_field_label(str(key))}\uff1a{_format_plan_value(value)}")



def render_workspace() -> None:
    active_view = st.session_state.get("active_view", "vector_store")
    if active_view == "vector_store":
        render_vector_store_panel()
    else:
        render_chat_panel()


if not st.session_state.get("token"):
    render_login_screen()
else:
    render_sidebar()
    render_user_menu()

    menu_view = st.session_state.get("menu_view", "")
    if menu_view == "profile":
        render_profile_view()
    elif menu_view == "change_password":
        render_change_password_view()
    else:
        render_workspace()
