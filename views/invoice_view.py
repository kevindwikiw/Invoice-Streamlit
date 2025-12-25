import streamlit as st
# import pandas as pd  <-- SUDAH DIHAPUS (NO PANDAS VERSION)
from uuid import uuid4
from datetime import datetime

# Import module internal
from modules import db
from modules import invoice as invoice_mod
from modules import gdrive

# Import UI components
from ui.components import page_header
from ui.formatters import rupiah

# ==========================================
# 1. STATE MANAGEMENT
# ==========================================
def _init_state():
    if "inv_items" not in st.session_state:
        st.session_state["inv_items"] = []
    
    st.session_state.setdefault("inv_client_name", "")
    st.session_state.setdefault("inv_client_email", "")
    st.session_state.setdefault("inv_no", f"INV/{datetime.now().strftime('%m')}/2026")
    st.session_state.setdefault("inv_cashback", 0)
    st.session_state.setdefault("bank_nm", "BCA") 
    st.session_state.setdefault("bank_an", "FANI PUSPITA")
    st.session_state.setdefault("bank_ac", "1234567890")
    
    # State untuk menyimpan PDF sementara biar gak ilang pas reload
    st.session_state.setdefault("generated_pdf_bytes", None) 

def reset_callback():
    st.session_state["inv_items"] = []
    st.session_state["inv_cashback"] = 0
    st.session_state["generated_pdf_bytes"] = None 


# ==========================================
# 2. KATALOG (PURE PYTHON + LABEL FIXED)
# ==========================================
def _render_catalog(data: list):
    st.markdown("### 🛍️ Katalog Paket")

    # --- A. Persiapan Filter ---
    all_cats = sorted(list(set(d.get("category", "Umum") for d in data)))
    cats_options = ["All"] + all_cats

    c_filter, c_search = st.columns([1, 2])
    with c_filter:
        selected_cat = st.selectbox("Kategori", cats_options, label_visibility="collapsed")
    with c_search:
        search_q = st.text_input("Search name…", label_visibility="collapsed", placeholder="Search name…")

    # --- B. Proses Filtering ---
    filtered = data
    if selected_cat != "All":
        filtered = [d for d in filtered if d.get("category") == selected_cat]

    if search_q:
        q_lower = search_q.lower()
        filtered = [d for d in filtered if q_lower in d.get("name", "").lower()]

    # --- C. Tampilkan Grid ---
    if not filtered:
        st.warning("Paket tidak ditemukan.")
        return

    COLS = 3
    rows = st.columns(COLS)
    
    # Ambil daftar nama item yang SEDANG ada di keranjang
    current_cart_names = [item["Description"] for item in st.session_state["inv_items"]]

    for idx, row in enumerate(filtered):
        with rows[idx % COLS]:
            with st.container(border=True):
                # 1. Ambil Kategori Asli ("Utama"/"Bonus")
                cat_name = row.get("category", "Umum")
                
                # 2. Tentukan Style & Text Badge
                is_main = (cat_name == "Utama")
                badge_class = "badge-main" if is_main else "badge-addon"
                
                # [UBAH DISINI] Logic ubah teks "Utama" jadi "MAIN"
                badge_text = "◆ MAIN" if is_main else "✨ ADD-ON"
                
                desc_text = str(row.get("description", ""))
                desc_html = desc_text.replace("\n", "<br>")
                price_val = float(row.get("price", 0))
                item_name = row.get("name", "Unnamed")
                item_id = row.get("id", idx)

                # 3. Render HTML (Perhatikan {badge_text} menggantikan {cat_name})
                st.markdown(f"""
                    <div style="margin-bottom: 10px;">
                      <div class="card-topbar">
                        <span class="badge {badge_class}">{badge_text}</span>
                      </div>
                      <div class="mini-title">{item_name}</div>
                      <div class="mini-price">{rupiah(price_val)}</div>
                      <div class="desc-clamp" style="margin-top: 8px; font-size: 0.8rem; color: #666;">{desc_html}</div>
                    </div>""", unsafe_allow_html=True)
                
                # --- LOGIC TOMBOL ADD/ADDED ---
                is_already_added = item_name in current_cart_names
                btn_label = "✓ Added" if is_already_added else "＋ Add"
                
                if st.button(btn_label, key=f"add_pos_{item_id}", disabled=is_already_added, use_container_width=True):
                    new_item = {
                        "__id": str(uuid4()), 
                        "Description": item_name, 
                        "Details": desc_text,
                        "Qty": 1, 
                        "Price": price_val, 
                        "Total": price_val
                    }
                    st.session_state["inv_items"].append(new_item)
                    st.session_state["generated_pdf_bytes"] = None # Reset PDF
                    st.toast(f"Ditambahkan: {item_name}", icon="🛒")
                    st.rerun()


# ==========================================
# 3. STRUK / KERANJANG BELANJA (LAYOUT LEGA)
# ==========================================
def _render_receipt():
    with st.container(border=True):
        st.markdown('<div class="ticket-header"><h4>🧾 Invoice Draft</h4></div>', unsafe_allow_html=True)
        
        c_nm, c_mail = st.columns([1, 1.2])
        with c_nm: st.text_input("Nama Klien", key="inv_client_name", placeholder="Cth: Budi Santoso")
        with c_mail: st.text_input("Email Gmail", key="inv_client_email", placeholder="client@gmail.com")

        st.text_input("No. Invoice", key="inv_no")
        st.markdown("<div class='summary-divider'></div>", unsafe_allow_html=True)

        items = st.session_state["inv_items"]
        subtotal = 0
        
        if not items:
            st.info("Keranjang kosong.")
        else:
            for i, item in enumerate(items):
                subtotal += (item["Price"] * item["Qty"])
                
                # --- LAYOUT BARU: TIDAK ADA NESTING KOLOM ---
                # 1. Baris Judul (Full Width)
                st.markdown(f"<div style='font-weight:700; font-size:0.9rem; color:var(--text); margin-bottom: 2px;'>{item['Description']}</div>", unsafe_allow_html=True)
                
                # 2. Baris Kontrol (Qty | Harga | Hapus)
                # Kita kasih Qty porsi [1.2] agar tombol -/+ punya ruang nafas
                c_qty, c_price, c_del = st.columns([1.2, 1.8, 0.6], vertical_alignment="bottom")
                
                with c_qty:
                    # Input Quantity
                    new_qty = st.number_input(
                        "Qty", 
                        min_value=1, 
                        value=int(item["Qty"]), 
                        key=f"qty_{item['__id']}", 
                        label_visibility="visible" # Tampilkan label kecil biar layout ga geser
                    )
                    if new_qty != item["Qty"]:
                        item["Qty"] = new_qty
                        item["Total"] = new_qty * item["Price"]
                        st.session_state["generated_pdf_bytes"] = None
                        st.rerun()

                with c_price:
                    # Info Harga (Rata Kanan dikit biar rapi)
                    total_item_price = item['Price'] * item['Qty']
                    st.markdown(f"""
                    <div style='font-size:0.8rem; color:#666; line-height:1.2; padding-bottom:10px;'>
                        @ {rupiah(item['Price'])}<br>
                        <b>= {rupiah(total_item_price)}</b>
                    </div>
                    """, unsafe_allow_html=True)

                with c_del:
                    # Tombol Hapus (Trash Icon)
                    if st.button("🗑", key=f"del_{item['__id']}", help="Hapus Item"):
                        st.session_state["inv_items"].pop(i)
                        st.session_state["generated_pdf_bytes"] = None
                        st.rerun()
                
                # Garis pemisah antar item
                st.markdown("<hr style='margin: 8px 0; border-top: 1px dashed #eee;'>", unsafe_allow_html=True)

        # --- CASHBACK & TOTAL ---
        st.write("")
        c_cb_label, c_cb_input = st.columns([2, 1.5], vertical_alignment="center")
        with c_cb_label: st.markdown("<div style='text-align:right; font-weight:600; color:#666;'>Potongan / Cashback (Rp):</div>", unsafe_allow_html=True)
        with c_cb_input:
            st.number_input("Cashback", min_value=0, step=10000, key="inv_cashback", label_visibility="collapsed")
        
        final_total = max(0, subtotal - st.session_state["inv_cashback"])

        if st.session_state["inv_cashback"] > 0:
            st.markdown(f"""
                <div style="display:flex; justify-content:space-between; padding: 0 10px; font-size:0.9rem; color:#666;">
                    <span>Subtotal</span><span>{rupiah(subtotal)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; padding: 0 10px; font-size:0.9rem; color:#d11a2a; margin-bottom:10px;">
                    <span>- Potongan</span><span>({rupiah(st.session_state["inv_cashback"])})</span>
                </div>""", unsafe_allow_html=True)

        st.markdown(f"""
            <div class="ticket-total-box">
                <small style="opacity:0.8;">TOTAL BAYAR</small>
                <div style="font-size:1.6rem; font-weight:800;">{rupiah(final_total)}</div>
            </div>""", unsafe_allow_html=True)
        
        st.write("")
        
        # --- TOMBOL AKSI ---
        c_act1, c_act2 = st.columns([1, 2])
        with c_act1:
            st.button("Reset", use_container_width=True, on_click=reset_callback)
            
        with c_act2:
            if st.button("🚀 PROSES PDF", type="primary", use_container_width=True, disabled=(final_total==0 and subtotal==0)):
                _generate_pdf_state(subtotal, st.session_state["inv_cashback"], final_total, items)
                st.rerun()

    if st.session_state.get("generated_pdf_bytes") is not None:
        _render_action_buttons()

# ==========================================
# 4. PDF GENERATION & ACTIONS
# ==========================================
def _generate_pdf_state(subtotal, cashback, final_total, items):
    client_name = st.session_state["inv_client_name"]
    inv_no = st.session_state["inv_no"]
    
    meta = {
        "client_name": client_name,
        "inv_no": inv_no,
        "bank_name": st.session_state.get("bank_nm", "BCA"),
        "bank_acc": st.session_state.get("bank_ac", "123"),
        "bank_holder": st.session_state.get("bank_an", "Admin"),
        "subtotal": subtotal,
        "cashback": cashback
    }
    
    pdf_bytes = invoice_mod.generate_pdf_bytes(meta, items, final_total)
    st.session_state["generated_pdf_bytes"] = pdf_bytes
    st.toast("PDF Berhasil dibuat!", icon="✅")


def _render_action_buttons():
    pdf_bytes = st.session_state["generated_pdf_bytes"]
    inv_no = st.session_state["inv_no"]
    client_email = st.session_state.get("inv_client_email", "")
    
    st.success("✅ PDF Siap!")
    
    with st.container(border=True):
        st.markdown("#### 📤 Pilih Metode Kirim")
        col_dl, col_drive = st.columns(2)
        
        with col_dl:
            st.download_button(
                label="📥 Download Lokal",
                data=pdf_bytes,
                file_name=f"{inv_no.replace('/', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with col_drive:
            if st.button("☁️ Save & Share Email", type="primary", use_container_width=True):
                if not client_email:
                    st.error("⚠️ Masukkan email dulu!")
                else:
                    with st.spinner("Mengupload ke Drive & Mengirim Email..."):
                        pdf_bytes.seek(0)
                        
                        success, link, msg = gdrive.upload_and_share(
                            pdf_bytes, 
                            f"{inv_no.replace('/', '_')}.pdf", 
                            client_email
                        )
                        
                        if success:
                            st.success("✅ Terkirim!")
                            st.caption(f"Status: {msg}")
                            st.link_button("📂 Lihat di Drive", url=link)
                        else:
                            st.error(f"Gagal: {msg}")


# ==========================================
# 5. MAIN RENDER PAGE
# ==========================================
def render_page():
    _init_state()
    page_header("Buat Invoice", "Input paket, download atau kirim via email.")
    
    left, right = st.columns([1.8, 1], gap="medium")
    
    # LOAD DATA & CONVERT TO LIST
    raw_data = db.load_packages() 
    if hasattr(raw_data, "to_dict"):
        raw_data = raw_data.to_dict("records")
    if raw_data is None:
        raw_data = []

    with left: 
        _render_catalog(raw_data)
        
    with right: 
        _render_receipt()
        st.write("")
        with st.expander("⚙️ Setting Akun Bank"):
            st.text_input("Nama Bank", key="bank_nm")
            st.text_input("No Rekening", key="bank_ac")
            st.text_input("Atas Nama", key="bank_an")
