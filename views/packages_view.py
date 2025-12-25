import streamlit as st
import pandas as pd
from modules import db
from ui.components import page_header, section, danger_container
from ui.formatters import rupiah

# =========================================================
# 0) CONSTANTS
# =========================================================
CATEGORIES = ["Utama", "Bonus"]          # add later: ["Utama","Bonus","Promo"]
CATEGORY_ALL = "All"

SORT_OPTIONS = {
    "Newest": ("id", False),
    "Price: High → Low": ("price", False),
    "Price: Low → High": ("price", True),
    "Name: A → Z": ("name", True),
}

GRID_OPTIONS = {"3 cols": 3, "4 cols": 4}

PAGE_SIZE_DEFAULT = 12
DESC_PREVIEW_LINES = 3


# =========================================================
# 1) DATA HELPERS
# =========================================================
def _safe_load_data() -> pd.DataFrame:
    """Load packages (cached by db.py) + normalize schema."""
    try:
        df = db.load_packages()
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "name", "price", "category", "description"])

    df = df.copy()
    if "category" not in df.columns:
        df["category"] = CATEGORIES[0]
    if "description" not in df.columns:
        df["description"] = ""

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["category"] = df["category"].fillna(CATEGORIES[0])
    df["description"] = df["description"].fillna("")
    df["name"] = df["name"].fillna("")
    return df


def _desc_meta(text: str, max_lines: int = DESC_PREVIEW_LINES):
    """
    Return:
      preview_html: bullet lines up to max_lines
      more_count: int
      full_lines: list[str]
    """
    lines = [x.strip() for x in str(text or "").split("\n") if x.strip()]
    if not lines:
        return "", 0, []

    preview = lines[:max_lines]
    preview_html = "<br>".join([f"• {ln}" for ln in preview])
    more_count = max(0, len(lines) - max_lines)
    return preview_html, more_count, lines


def _apply_filters(df: pd.DataFrame, q: str, cat: str) -> pd.DataFrame:
    out = df
    if q:
        out = out[out["name"].str.contains(q, case=False, na=False)]
    if cat != CATEGORY_ALL:
        out = out[out["category"] == cat]
    return out


def _apply_sort(df: pd.DataFrame, sort_label: str) -> pd.DataFrame:
    col, asc = SORT_OPTIONS.get(sort_label, ("id", False))
    if col not in df.columns:
        return df
    return df.sort_values(col, ascending=asc)


# =========================================================
# 2) FORM (EDIT: NO DELETE BUTTON, biar ga double)
# =========================================================
def _render_package_form(data: dict | None = None, key_prefix: str = "pkg"):
    is_edit = data is not None
    defaults = {
        "name": data.get("name", "") if is_edit else "",
        "cat": data.get("category", CATEGORIES[0]) if is_edit else CATEGORIES[0],
        "price": int(float(data.get("price", 0))) if is_edit else 0,
        "desc": data.get("description", "") if is_edit else "",
    }

    with st.container():
        name = st.text_input(
            "Package Name",
            value=defaults["name"],
            placeholder="e.g. Platinum Wedding Bundle",
            key=f"{key_prefix}_name",
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            cat_idx = CATEGORIES.index(defaults["cat"]) if defaults["cat"] in CATEGORIES else 0
            category = st.selectbox("Category", CATEGORIES, index=cat_idx, key=f"{key_prefix}_cat")
        with c2:
            price = st.number_input(
                "Price (IDR)",
                min_value=0,
                step=50000,
                value=defaults["price"],
                key=f"{key_prefix}_price",
            )
            if price > 0:
                st.caption(f"Display: **{rupiah(price)}**")

        st.write("")
        st.markdown("**🧾 Package Details / Items**")
        st.caption("Tulis satu item per baris. Tekan ENTER untuk baris baru.")

        description = st.text_area(
            "Description",
            value=defaults["desc"],
            height=220,
            label_visibility="collapsed",
            placeholder="1 Photographer\n1 Videographer\nAlbum 20 Pages",
            key=f"{key_prefix}_desc",
        )

        st.divider()

        c_save, c_close = st.columns([1, 1])
        with c_save:
            btn_label = "💾 Save Changes" if is_edit else "➕ Create Package"
            is_save = st.button(btn_label, type="primary", use_container_width=True, key=f"{key_prefix}_save")
        with c_close:
            is_close = st.button("✕ Close", use_container_width=True, key=f"{key_prefix}_close")

        payload = {
            "name": name.strip(),
            "category": category,
            "price": float(price),
            "description": description.strip(),
        }
        return is_save, is_close, payload


# =========================================================
# 3) DIALOGS (ESC/CANCEL SAFE via modal pop)
# =========================================================
@st.dialog("➕ Add New Package")
def show_add_dialog():
    is_save, is_close, payload = _render_package_form(data=None, key_prefix="add_new")

    if is_close:
        st.rerun()

    if is_save:
        if not payload["name"]:
            st.error("⚠️ Package name is required.")
            return
        try:
            db.add_package(payload["name"], payload["price"], payload["category"], payload["description"])
        except Exception as e:
            st.error("Gagal menyimpan package. Coba ulangi.")
            st.caption(f"Debug: {e}")
            return

        st.toast("Package created!", icon="✅")
        st.rerun()


@st.dialog("✏️ Edit Package")
def show_edit_dialog(row_data: dict):
    pkg_id = int(row_data["id"])
    is_save, is_close, payload = _render_package_form(row_data, key_prefix=f"edit_{pkg_id}")

    if is_close:
        st.rerun()

    if is_save:
        if not payload["name"]:
            st.error("⚠️ Name is required.")
            return
        try:
            db.update_package(pkg_id, payload["name"], payload["price"], payload["category"], payload["description"])
        except Exception as e:
            st.error("Gagal menyimpan perubahan. Coba ulangi.")
            st.caption(f"Debug: {e}")
            return

        st.toast("Saved!", icon="💾")
        st.rerun()


@st.dialog("🗑️ Delete Package")
def show_delete_dialog(row_data: dict):
    pkg_id = int(row_data["id"])
    name = row_data.get("name", "")

    st.markdown(
        f"""
        <div style="text-align:center; padding: 18px 0;">
          <div style="font-size: 48px; margin-bottom: .75rem;">🗑️</div>
          <div style="font-weight:900; font-size: 1.05rem; color:#1a1a1a;">Delete this package?</div>
          <div style="color:#666; font-size:.92rem; margin-top:.35rem;">
            <b>"{name}"</b> will be permanently removed.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True, key=f"cancel_del_{pkg_id}"):
        st.rerun()

    with c2:
        with danger_container(key=f"danger_confirm_{pkg_id}"):
            if st.button("Yes, Delete", type="primary", use_container_width=True, key=f"confirm_del_{pkg_id}"):
                try:
                    db.delete_package(pkg_id)
                except Exception as e:
                    st.error("Gagal delete package. Coba ulangi.")
                    st.caption(f"Debug: {e}")
                    return

                st.toast("Deleted.", icon="🗑️")
                st.rerun()


# =========================================================
# 4) GRID
# =========================================================
def _render_grid(df: pd.DataFrame, cols_count: int, page_size: int = PAGE_SIZE_DEFAULT):
    st.session_state.setdefault("_pkg_page", 1)

    total = len(df)
    if total == 0:
        st.info("No results.")
        return

    max_page = max(1, (total + page_size - 1) // page_size)
    st.session_state["_pkg_page"] = min(st.session_state["_pkg_page"], max_page)

    p1, p2, p3 = st.columns([1, 2, 1])
    with p1:
        if st.button("← Prev", use_container_width=True, disabled=(st.session_state["_pkg_page"] <= 1)):
            st.session_state["_pkg_page"] -= 1
            st.rerun()
    with p2:
        st.markdown(
            f"<div style='text-align:center; color:#6e6e73; padding-top:.35rem;'>Page <b>{st.session_state['_pkg_page']}</b> / {max_page} • Total <b>{total}</b></div>",
            unsafe_allow_html=True,
        )
    with p3:
        if st.button("Next →", use_container_width=True, disabled=(st.session_state["_pkg_page"] >= max_page)):
            st.session_state["_pkg_page"] += 1
            st.rerun()

    start = (st.session_state["_pkg_page"] - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end]

    cols = st.columns(cols_count)
    for idx, row in enumerate(page_df.itertuples(index=False)):
        with cols[idx % cols_count]:
            is_main = (row.category == CATEGORIES[0])
            badge_class = "badge-main" if is_main else "badge-addon"
            badge_text = "◆ MAIN" if is_main else "✨ ADD-ON"

            preview_html, more, full_lines = _desc_meta(row.description, max_lines=DESC_PREVIEW_LINES)
            full_html = "".join([f"<div class='desc-tooltip-line'>• {ln}</div>" for ln in full_lines])

            tooltip_html = ""
            if more > 0:
                tooltip_html = (
                    "<div class='desc-tooltip'>"
                    "<div class='desc-tooltip-title'>📋 Full details</div>"
                    f"{full_html}"
                    "</div>"
                )

            if preview_html:
                details_html = f"<div class='desc-clamp'>{preview_html}</div>"
            else:
                details_html = "<div class='mini-muted' style='margin-top:10px;'>No details.</div>"

            more_html = f"<div class='desc-more'>+{more} more…</div>" if more > 0 else ""

            st.markdown(
                f"""
                <div class="mini-card">
                  <div class="card-topbar">
                    <span class="badge {badge_class}">{badge_text}</span>
                  </div>

                  <div class="mini-title">{row.name}</div>
                  <div class="mini-price">{rupiah(row.price)}</div>

                  <div class="mini-body">
                    {details_html}
                    {more_html}
                  </div>

                  {tooltip_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<div class='card-actions-gap'></div>", unsafe_allow_html=True)

            a1, a2 = st.columns([1, 1])
            with a1:
                if st.button("✏️ Edit", key=f"grid_edit_{row.id}", use_container_width=True):
                    st.session_state["_pkg_modal"] = ("edit", int(row.id))
                    st.rerun()

            with a2:
                with danger_container(key=f"danger_card_{row.id}"):
                    if st.button("🗑️ Delete", key=f"grid_del_{row.id}", use_container_width=True):
                        st.session_state["_pkg_modal"] = ("delete", int(row.id))
                        st.rerun()

            st.write("")


# =========================================================
# 5) PAGE
# =========================================================
def render_page():
    page_header(
        "📦 Packages Database",
        "Kelola katalog harga dengan rapi — konsisten nama, harga, dan itemnya.",
    )

    df = _safe_load_data()

    # IMPORTANT:
    # modal state dikonsumsi (pop) sebelum panggil dialog,
    # jadi ESC/CANCEL tidak bikin modal kebuka lagi di rerun berikutnya.
    modal = st.session_state.pop("_pkg_modal", None)
    if modal:
        mode, pkg_id = modal
        if mode == "add":
            show_add_dialog()
        elif mode in ("edit", "delete") and isinstance(pkg_id, int):
            row = df[df["id"] == pkg_id]
            if not row.empty:
                if mode == "edit":
                    show_edit_dialog(row.iloc[0].to_dict())
                else:
                    show_delete_dialog(row.iloc[0].to_dict())

    st.write("")

    c1, c2, c3, c4, c5 = st.columns([2.2, 1.1, 1.2, 1.0, 1.35], vertical_alignment="bottom")
    with c1:
        q = st.text_input("🔎 Search", placeholder="Search name…", key="pkg_search")
    with c2:
        cat = st.selectbox("🏷️ Category", [CATEGORY_ALL] + CATEGORIES, key="pkg_cat")
    with c3:
        sort = st.selectbox("↕️ Sort", list(SORT_OPTIONS.keys()), key="pkg_sort")
    with c4:
        grid_label = st.selectbox("🧩 Grid", list(GRID_OPTIONS.keys()), index=1, key="pkg_grid_cols")
        cols_count = GRID_OPTIONS[grid_label]
    with c5:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("＋ Create", type="primary", use_container_width=True, key="pkg_create_btn"):
            st.session_state["_pkg_modal"] = ("add", None)
            st.rerun()

    sig = (q, cat, sort, cols_count)
    if st.session_state.get("_pkg_sig") != sig:
        st.session_state["_pkg_sig"] = sig
        st.session_state["_pkg_page"] = 1

    filtered = _apply_filters(df, q, cat)
    filtered = _apply_sort(filtered, sort)

    st.caption(f"📌 Showing **{len(filtered)}** of **{len(df)}** packages.")
    st.write("")

    section("✨ Catalog Cards")

    if filtered.empty:
        st.info("No packages match your search. Coba keyword/kategori lain.")
        return

    _render_grid(filtered, cols_count=cols_count, page_size=PAGE_SIZE_DEFAULT)
