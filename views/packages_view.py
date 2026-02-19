import streamlit as st
from modules import db
from views.styles import page_header, section, danger_container
from ui.formatters import rupiah
from views.styles import inject_styles


# =========================================================
# 0) CONSTANTS
# =========================================================
CATEGORIES = [
  "Wedding",
  "Bundling Package",
  "Prewedding",
  "Engagement/Sangjit",
  "Corporate/Event",
  "Add-ons",
  "Free / Complimentary"
]
CATEGORY_ALL = "All"

# Format Sort: (key_dictionary, is_ascending)
SORT_OPTIONS = {

    "Price: High → Low": ("price", False),
    "Price: Low → High": ("price", True),
    "Name: A → Z": ("name", True),
}



PAGE_SIZE_DEFAULT = 9
DESC_PREVIEW_LINES = 3


# =========================================================
# 1) DATA HELPERS (PURE PYTHON VERSION)
# =========================================================
def _safe_load_data(active_only: bool = True) -> list:
    """Load packages and convert to list of dicts."""
    try:
        # Asumsi db.load_packages() mengembalikan list of dicts
        # Kalau dia balikin Pandas DataFrame, kita convert manual:
        raw_data = db.load_packages(active_only=active_only)
        
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
            "description": str(item.get("description") or ""),
            "is_active": int(item.get("is_active", 1)),
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
# 2) FORM HELPERS & COMPONENT
# =========================================================

def _parse_bundle_description(desc: str) -> list[dict]:
    """
    Parses a description string into list of items if it follows the bundle format.
    Format:
    **Title**
    Lines...
    
    **Title 2**
    Lines...
    """
    import re
    if not desc:
        return [{"title": "", "details": ""}, {"title": "", "details": ""}]

    # Regex to find **Title** followed by content until next **Title** or end
    # Note: This is a simple parser.
    parts = re.split(r'\n\s*\n', desc.strip())
    
    items = []
    current_item = {"title": "", "details": ""}
    
    # Heuristic: Check if parts look like bundle items
    # If not bundle format, return single item with full desc
    is_bundle_format = any(p.strip().startswith("**") and "**" in p.strip()[2:] for p in parts)
    
    if not is_bundle_format and "**" not in desc:
         return [{"title": "Package Details", "details": desc}]

    # Robust parsing
    raw_sections = re.split(r'(?:\n|^)\*\*([^*]+)\*\*(?:\n|$)', desc)
    # Result: [pre_text, title1, body1, title2, body2, ...]
    
    if len(raw_sections) < 3:
         # Fallback
         return [{"title": "Package Details", "details": desc}]
         
    # Skip index 0 (pre_text usually empty)
    for i in range(1, len(raw_sections), 2):
        t = raw_sections[i].strip()
        d = raw_sections[i+1].strip() if i+1 < len(raw_sections) else ""
        items.append({"title": t, "details": d})
        
    while len(items) < 2:
        items.append({"title": "", "details": ""})
        
    return items

def _generate_bundle_description(items: list[dict]) -> str:
    """Combines items into formatted Markdown string."""
    chunks = []
    for it in items:
        t = it.get("title", "").strip()
        d = it.get("details", "").strip()
        if t or d:
            if t:
                chunks.append(f"**{t}**\n{d}")
            else:
                chunks.append(d)
    return "\n\n".join(chunks)


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
            try:
                cat_idx = CATEGORIES.index(defaults["cat"])
            except ValueError:
                cat_idx = 0
            
            # Auto-detect category change for UI toggle
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
        
        # --- BUNDLE BUILDER UI LOGIC ---
        is_bundle_cat = (category == "Bundling Package")
        
        # State key for toggling modes (if user wants raw edit even in bundle cat)
        k_mode = f"{key_prefix}_mode"
        if k_mode not in st.session_state:
            st.session_state[k_mode] = "builder" if is_bundle_cat else "raw"
            
        # If Category changed to/from Bundle, auto-switch mode ONLY if not manually set recently?
        # Simpler: If Category is Bundle, default to builder. User can switch to raw.
        
        if is_bundle_cat:
            b_uv, b_parse = st.columns([0.7, 0.3], vertical_alignment="bottom")
            with b_uv:
                 st.info("💡 **Bundle Mode Active**: Add multiple sub-packages below.")
            with b_parse:
                # Toggle
                current_mode = st.session_state[k_mode]
                if current_mode == "builder":
                    if st.button("📝 Switch to Raw Text", key=f"{key_prefix}_to_raw", use_container_width=True):
                        st.session_state[k_mode] = "raw"
                        st.rerun()
                else:
                    if st.button("🧩 Switch to Builder", key=f"{key_prefix}_to_builder", use_container_width=True):
                        st.session_state[k_mode] = "builder"
                        st.rerun()
        
        final_description = defaults["desc"]
        
        # RENDER BUILDER
        if is_bundle_cat and st.session_state[k_mode] == "builder":
            # 1. Parse existing desc into Items
            # We use st.session_state to hold temp builder values to prevent loss on rerun
            k_items = f"{key_prefix}_b_items"
            
            # Initial Load
            if k_items not in st.session_state:
                st.session_state[k_items] = _parse_bundle_description(defaults["desc"])
            
            items = st.session_state[k_items]
            
            # Render Inputs
            for idx, item in enumerate(items):
                with st.container():
                     st.markdown(f"**Item {idx+1}**")
                     c_t, c_d = st.columns([1, 2])
                     with c_t:
                         new_t = st.text_input(f"Title {idx+1}", value=item["title"], key=f"{key_prefix}_b_t_{idx}", placeholder="e.g. Wedding")
                         items[idx]["title"] = new_t
                     with c_d:
                         new_d = st.text_area(f"Details {idx+1}", value=item["details"], height=100, key=f"{key_prefix}_b_d_{idx}", placeholder="- Item 1\n- Item 2")
                         items[idx]["details"] = new_d
            
            # Add / Remove Buttons
            ba1, ba2 = st.columns([1, 4])
            with ba1:
                if st.button("＋ Add Item", key=f"{key_prefix}_add_item"):
                    items.append({"title": "", "details": ""})
                    st.rerun()
            
            # Generate Description Live
            final_description = _generate_bundle_description(items)
            
            # Preview
            with st.expander("👀 Live Preview (Result)", expanded=False):
                st.markdown(final_description)
                
        else:
            # RAW TEXT MODE (Standard)
            if is_bundle_cat:
                 st.caption("Mode Manual: Gunakan format **Title** untuk memisahkan paket.")
                 placeholder_text = "**Wedding**\n- Item 1\n- Item 2\n\n**Prewedding**\n- Item A\n- Item B"
            else:
                 st.caption("Tulis satu item per baris. Tekan ENTER untuk baris baru.")
                 placeholder_text = "1 Photographer\n1 Videographer\nAlbum 20 Pages"

            final_description = st.text_area(
                "Description",
                value=defaults["desc"],
                height=220,
                label_visibility="collapsed",
                placeholder=placeholder_text,
                key=f"{key_prefix}_desc",
            )
            # Clean up builder state if checking raw
            if f"{key_prefix}_b_items" in st.session_state:
                del st.session_state[f"{key_prefix}_b_items"]

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
            "description": final_description.strip(),
        }
        return is_save, is_close, payload


# =========================================================
# 3) DIALOGS
# =========================================================
@st.dialog("➕ Add New Package", width="large")
def show_add_dialog():
    is_save, is_close, payload = _render_package_form(data=None, key_prefix="add_new")

    if is_close:
        del st.session_state["_pkg_modal"]
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
        st.cache_data.clear()
        del st.session_state["_pkg_modal"]
        st.rerun()


@st.dialog("✏️ Edit Package", width="large")
def show_edit_dialog(row_data: dict):
    pkg_id = int(row_data["id"])
    is_save, is_close, payload = _render_package_form(row_data, key_prefix=f"edit_{pkg_id}")

    if is_close:
        del st.session_state["_pkg_modal"]
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
        st.cache_data.clear()
        del st.session_state["_pkg_modal"]
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
                st.cache_data.clear()
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
            # Use reusable component
            from views.styles import render_package_card
            

            
            # Truncate description for card view
            preview_html, more_count, _ = _desc_meta(row['description'])
            
            # Use the existing render_package_card but we might need to adjust it if it doesn't take raw HTML or list.
            # Wait, render_package_card in views.styles likely takes a list or string.
            # Let's look at how sidebar uses it: description=lines (list).
            # existing usage here: description=row['description'] (string).
            # I will pass the truncated list of lines.
            
            _, _, all_lines = _desc_meta(row['description'])
            display_lines = all_lines[:3]
            if len(all_lines) > 3:
                display_lines.append(f"... (+{len(all_lines)-3} more)")

            card_html = render_package_card(
                name=row['name'],
                price=row['price'],
                description=display_lines, # Pass list
                category=row['category'],
                is_main=is_main,
                compact=False,
                rupiah_formatter=rupiah,
                full_description=all_lines # Pass full text for hover
            )

            st.markdown(card_html, unsafe_allow_html=True)

            # Action Buttons: [Edit] [Archive/Restore] [Delete]
            b1, b2, b3 = st.columns([1, 1, 1], gap="small")
            
            with b1:
                # EDIT
                if st.button("✏️", key=f"grid_edit_{row['id']}", help="Edit Package", use_container_width=True):
                    st.session_state["_pkg_modal"] = ("edit", int(row['id']))
                    st.rerun()

            is_active = row.get('is_active', 1)
            
            with b2:
                # TOGGLE STATUS
                if is_active:
                    if st.button("📦", key=f"grid_arch_{row['id']}", help="Archive", use_container_width=True):
                        db.toggle_package_status(int(row['id']), False)
                        st.toast(f"Archived '{row['name']}'", icon="📦")
                        st.rerun()
                else:
                    if st.button("♻️", key=f"grid_rest_{row['id']}", help="Restore", use_container_width=True):
                        db.toggle_package_status(int(row['id']), True)
                        st.toast(f"Restored '{row['name']}'", icon="♻️")
                        st.rerun()

            with b3:
                # DELETE (Only if Archived for Safety, or Always?)
                # User asked for "3 buttons", implying all visible?
                # If Active, user SHOULD Archive first. So maybe disable Delete or hide it?
                # "hapus juga ntar gaibisa haapus numpu" -> implied they want to delete OLD stuff (Archived).
                # I'll show Delete ONLY if Archived to enforce the flow, or disabled if Active.
                if not is_active:
                     if st.button("🗑️", key=f"grid_del_{row['id']}", type="primary", help="Delete Permanently", use_container_width=True):
                        st.session_state["_pkg_modal"] = ("delete", int(row['id']))
                        st.rerun()
                else:
                     # Placeholder to keep alignment or disabled button
                     st.button("🗑️", key=f"grid_del_dis_{row['id']}", disabled=True, help="Archive first to delete", use_container_width=True)

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

    # Data Loading (Load ALL for filtering and modal lookup)
    all_data = _safe_load_data(active_only=False) 

    # Modal handling
    # modal = st.session_state.pop("_pkg_modal", None) # Default pop causes close on rerun
    modal = st.session_state.get("_pkg_modal", None)
    if modal:
        mode, pkg_id = modal
        if mode == "add":
            show_add_dialog()
        elif mode in ("edit", "delete") and isinstance(pkg_id, int):
            # Find data in all_data (including archived)
            found_rows = [d for d in all_data if d["id"] == pkg_id]
            if found_rows:
                row_dict = found_rows[0]
                if mode == "edit":
                    show_edit_dialog(row_dict)
                else:
                    show_delete_dialog(row_dict)
            else:
                # ID not found
                del st.session_state["_pkg_modal"]
                st.rerun()

    st.write("")

    # Layout: Search | Category | Status | Sort | Create
    c1, c2, c3, c4, c5 = st.columns([2, 1.2, 1.2, 1.2, 1.2], vertical_alignment="bottom")
    with c1:
        q = st.text_input("🔎 Search", placeholder="Search name…", key="pkg_search")
    with c2:
        cat = st.selectbox("🏷️ Category", [CATEGORY_ALL] + CATEGORIES, key="pkg_cat")
    with c3:
        status_filter = st.selectbox("👁️ Status", ["Active", "Archived", "All"], index=0, key="pkg_status")
    with c4:
        sort = st.selectbox("↕️ Sort", list(SORT_OPTIONS.keys()), key="pkg_sort")    
    with c5:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("＋ Create", type="primary", use_container_width=True, key="pkg_create_btn"):
            st.session_state["_pkg_modal"] = ("add", None)
            st.rerun()

    # Filter by Status
    if status_filter == "Active":
        data = [d for d in all_data if d.get('is_active', 1)]
    elif status_filter == "Archived":
        data = [d for d in all_data if not d.get('is_active', 1)]
    else:
        data = all_data

    cols_count = 3
    sig = (q, cat, status_filter, sort) 
    if st.session_state.get("_pkg_sig") != sig:
        st.session_state["_pkg_sig"] = sig
        st.session_state["_pkg_page"] = 1

    # Apply Logic Manual (List Comprehension)
    filtered_data = _apply_filters(data, q, cat)
    sorted_data = _apply_sort(filtered_data, sort)

    st.caption(f"📌 Showing **{len(sorted_data)}** of **{len(all_data)}** packages (Status: {status_filter})")
    st.write("")

    section("✨ Catalog Cards")

    if not sorted_data:
        st.info("No packages match your search.")
        return

    _render_grid(sorted_data, cols_count=cols_count, page_size=PAGE_SIZE_DEFAULT)
