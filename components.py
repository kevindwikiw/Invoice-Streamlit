import streamlit as st
from contextlib import contextmanager
from typing import Optional


def _next_key(prefix: str) -> str:
    """Generate a unique key per session (anti duplicate key)."""
    st.session_state.setdefault("_ui_seq", 0)
    st.session_state["_ui_seq"] += 1
    return f"{prefix}_{st.session_state['_ui_seq']}"


def page_header(title: str, subtitle: str | None = None):
    """Consistent page title + subtitle (match theme.py)."""
    st.markdown(f"<h1 class='page-title'>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='page-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def section(title: str):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def col_header(text: str):
    st.markdown(f"<div class='col-header'>{text}</div>", unsafe_allow_html=True)


def danger_container(key: Optional[str] = None):
    """
    Container wrapper untuk styling tombol danger.
    Key otomatis unik biar nggak StreamlitDuplicateElementKey.
    Theme kamu target selector data-key^="danger".
    """
    if not key:
        key = _next_key("danger")
    if not str(key).startswith("danger"):
        key = f"danger_{key}"
    return st.container(key=key)


@contextmanager
def muted_container():
    with st.container():
        st.markdown("<div style='color: var(--muted)'>", unsafe_allow_html=True)
        try:
            yield
        finally:
            st.markdown("</div>", unsafe_allow_html=True)
