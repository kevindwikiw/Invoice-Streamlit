import streamlit as st
from modules import db
from ui.components import page_header, section, danger_container
from ui.formatters import rupiah
from views.styles import inject_styles


# =========================================================
# 0) CONSTANTS
# =========================================================
CATEGORIES = ["Utama", "Bonus"]
CATEGORY_ALL = "All"

# Format Sort: (key_dictionary, is_ascending)
SORT_OPTIONS = {

    "Price: High → Low": ("price", False),
    "Price: Low → High": ("price", True),
    "Name: A → Z": ("name", True),
}

GRID_OPTIONS = {"3 cols": 3, "4 cols": 4}

PAGE_SIZE_DEFAULT = 12
DESC_PREVIEW_LINES = 3


# =========================================================
# 1) DATA HELPERS (PURE PYTHON VERSION)
# =========================================================
def _safe_load_data() -> list:
    """Load packages and convert to list of dicts."""
    try:
        # Asumsi db.load_packages() mengembalikan list of dicts
        # Kalau dia balikin Pandas DataFrame, kita convert manual:
        raw_data = db.load_packages()
        
        # Cek jika raw_data adalah DataFrame (jaga-jaga kalau db.py belum diubah)
        if hasattr(raw_data, 'to_dict'):
            data = raw_data.to_dict('records')
        else:
            data = raw_data
            
    except Exception:
        data = []

    if not data:
        return []

    # Normalize data (fillna manual)
    cleaned_data = []
    for item in data:
        # Pastikan item adalah dictionary
        if not isinstance(item, dict): continue
        
        cleaned_data.append({
            "id": int(item.get("id") or 0),
            "name": str(item.get("name") or ""),
            "price": float(item.get("price") or 0),
            "category": str(item.get("category") or CATEGORIES[0]),
            "description": str(item.get("description") or "")
        })
        
    return cleaned_data


def _desc_meta(text: str, max_lines: int = DESC_PREVIEW_LINES):
    lines = [x.strip() for x in str(text or "").split("\n") if x.strip()]
    if not lines:
        return "", 0, []

    preview = lines[:max_lines]
    preview_html = "<br>".join([f"• {ln}" for ln in preview])
    more_count = max(0, len(lines) - max_lines)
    return preview_html, more_count, lines


def _apply_filters(data: list, q: str, cat: str) -> list:
    filtered = data
    
    # Filter by Category
    if cat != CATEGORY_ALL:
        filtered = [d for d in filtered if d["category"] == cat]
    
    # Filter by Search Query (Name)
    if q:
        q_lower = q.lower()
        filtered = [d for d in filtered if q_lower in d["name"].lower()]
        
    return filtered


def _apply_sort(data: list, sort_label: str) -> list:
    col, asc = SORT_OPTIONS.get(sort_label, ("id", False))
    
    # Python Sort (List of Dicts)
    # reverse=True artinya Descending (Kebalikan dari logic Pandas 'ascending')
    return sorted(data, key=lambda x: x.get(col, 0), reverse=not asc)


# =========================================================
# 2) FORM
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
            # Handle index error safety
            try:
                cat_idx = CATEGORIES.index(defaults["cat"])
            except ValueError:
                cat_idx = 0
                
            category = st.selectbox("Category", CATEGORIES, index=cat_idx, key=f"{key_prefix}_cat")
        with c2:
            price = st.number_input(
                "Price (IDR)",
                min_value=0,
                step=250000,
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
# 3) DIALOGS
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
            st.error("Gagal menyimpan package.")
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
            st.error("Gagal menyimpan perubahan.")
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
                    st.error("Gagal delete package.")
                    st.caption(f"Debug: {e}")
                    return

                st.toast("Deleted.", icon="🗑️")
                st.rerun()


# =========================================================
# 4) GRID (PURE PYTHON)
# =========================================================
def _render_grid(data: list, cols_count: int, page_size: int = PAGE_SIZE_DEFAULT):
    st.session_state.setdefault("_pkg_page", 1)

    total = len(data)
    if total == 0:
        st.info("No results.")
        return

    max_page = max(1, (total + page_size - 1) // page_size)
    st.session_state["_pkg_page"] = min(st.session_state["_pkg_page"], max_page)

    # Navigation UI
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

    # Slice List manually
    start = (st.session_state["_pkg_page"] - 1) * page_size
    end = start + page_size
    page_data = data[start:end]

    cols = st.columns(cols_count)
    
    # Loop over list of dicts (bukan itertuples lagi)
    for idx, row in enumerate(page_data):
        with cols[idx % cols_count]:
            is_main = (row['category'] == CATEGORIES[0])
            bg_color, txt_color = ("#e8f5e9", "#15803d") if is_main else ("#fff7ed", "#c2410c")
            badge_text = "MAIN" if is_main else "ADD-ON"

            preview_html, more, full_lines = _desc_meta(row['description'], max_lines=DESC_PREVIEW_LINES)
            
            # Build tooltip for hover (same as invoice_view)
            tooltip_html = ""
            if full_lines and more > 0:
                full_html = "".join([f"<div>• {ln}</div>" for ln in full_lines])
                tooltip_html = (
                    "<div class='tip'><b>📋 Full Details</b>"
                    f"<div style='margin-top:6px;'>{full_html}</div></div>"
                )

            # Description preview
            if preview_html:
                desc_display = preview_html.replace("\n", "<br/>")
            else:
                desc_display = "No details."
                
            more_text = f"<div style='color:#3b82f6; font-size:.75rem; margin-top:4px;'>+{more} more…</div>" if more > 0 else ""

            st.markdown(
                f"""
                <div class="card" style="border:1px solid #f3f4f6;">
                  <span class="pill" style="background:{bg_color}; color:{txt_color};">{badge_text}</span>
                  <div class="title">{row['name']}</div>
                  <div class="price">{rupiah(row['price'])}</div>
                  <div class="desc">{desc_display}{more_text}</div>
                  {tooltip_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Action Buttons (Edit / Delete)
            a1, a2 = st.columns([1, 1])
            with a1:
                if st.button("✏️ Edit", key=f"grid_edit_{row['id']}", use_container_width=True):
                    st.session_state["_pkg_modal"] = ("edit", int(row['id']))
                    st.rerun()

            with a2:
                with danger_container(key=f"danger_card_{row['id']}"):
                    if st.button("🗑️ Delete", key=f"grid_del_{row['id']}", use_container_width=True):
                        st.session_state["_pkg_modal"] = ("delete", int(row['id']))
                        st.rerun()

            st.write("")


# =========================================================
# 5) PAGE
# =========================================================
def render_page():
    inject_styles()
    page_header(
        "📦 Packages Database",
        "Streamline your service catalog. Ensure consistency in package names, pricing, and details for accurate invoicing.",
    )

    data = _safe_load_data() # Sekarang balikin List, bukan DataFrame

    # Modal handling
    modal = st.session_state.pop("_pkg_modal", None)
    if modal:
        mode, pkg_id = modal
        if mode == "add":
            show_add_dialog()
        elif mode in ("edit", "delete") and isinstance(pkg_id, int):
            # Cari data manual di list (filter)
            found_rows = [d for d in data if d["id"] == pkg_id]
            if found_rows:
                row_dict = found_rows[0] # Sudah dict, gak perlu to_dict()
                if mode == "edit":
                    show_edit_dialog(row_dict)
                else:
                    show_delete_dialog(row_dict)

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

    # Apply Logic Manual (List Comprehension)
    filtered_data = _apply_filters(data, q, cat)
    sorted_data = _apply_sort(filtered_data, sort)

    st.caption(f"📌 Showing **{len(sorted_data)}** of **{len(data)}** packages.")
    st.write("")

    section("✨ Catalog Cards")

    if not sorted_data:
        st.info("No packages match your search. Coba keyword/kategori lain.")
        return

    _render_grid(sorted_data, cols_count=cols_count, page_size=PAGE_SIZE_DEFAULT)
