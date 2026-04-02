import streamlit as st

from project_config import SETTINGS


def ensure_session_defaults() -> None:
    defaults = {
        "token": "",
        "username": "",
        "email": "",
        "chat_history": [],
        "documents": [],
        "top_k": SETTINGS.final_top_k,
        "active_view": "vector_store",
        "menu_view": "",
        "nav_view_label": "\u5411\u91cf\u5e93",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def logout_user() -> None:
    # Widget-backed keys such as `top_k` must be removed instead of reassigned
    # after the corresponding widget has already been created in the same run.
    for key in (
        "token",
        "username",
        "email",
        "chat_history",
        "documents",
        "top_k",
        "active_view",
        "menu_view",
        "nav_view_label",
    ):
        st.session_state.pop(key, None)
