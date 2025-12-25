import streamlit as st
import pandas as pd
from uuid import uuid4
from datetime import datetime

# Import module internal
from modules import db
from modules import invoice as invoice_mod
from modules import gdrive

# Import UI components
from ui.components import page_header
from ui.formatters import rupiah

# --- STATE INIT ---
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
    
    # [BARU] State untuk menyimpan PDF sementara biar gak ilang pas reload
    st.session_state.setdefault("generated_pdf_bytes", None) 

# --- HELPER: RESET CALLBACK ---
def reset_callback():
    st.session_state["inv_items"] = []
    st.session_state["inv_cashback"] = 0
    st.session_state["generated_pdf_bytes"] = None # Reset juga PDF-nya

# --- KIRI: KATALOG (Sama persis, saya skip biar ringkas) ---
def _render_catalog(df):
    # ... (Copy paste code katalog kamu yang lama di sini) ...
    # Bagian ini aman, tidak ada perubahan logic
    st.markdown("### 🛍️ Katalog Paket")
    c_filter, c_search = st.columns([1, 2])
    with c_filter:
        cats = ["All"] + list(df["category"].unique()) if "category" in df.columns else ["All"]
        selected_cat = st.selectbox("Kategori", cats, label_visibility="collapsed")
    with c_search:
        search_q = st.text_input("Cari paket...", label_visibility="collapsed", placeholder="🔍 Cari nama paket...")

    filtered = df.copy()
    if selected_cat != "All":
        filtered = filtered[filtered["category"] == selected_cat]
    if search_q:
        filtered = filtered[filtered["name"].str.contains(search_q, case=False)]

    if filtered.empty:
        st.warning("Paket tidak ditemukan.")
        return

    COLS = 3
    rows = st.columns(COLS)
    
    for idx, row in enumerate(filtered.itertuples()):
        with rows[idx % COLS]:
            with st.container(border=True):
                is_main = (row.category == "Utama")
                badge_class = "badge-main" if is_main else "badge-addon"
                desc_text = str(row.description) if row.description else ""
                desc_html = desc_text.replace("\n", "<br>")

                st.markdown(f"""
                    <div style="margin-bottom: 10px;">
                      <div class="card-topbar"><span class="badge {badge_class}">{row.category}</span></div>
                      <div class="mini-title">{row.name}</div>
                      <div class="mini-price">{rupiah(row.price)}</div>
                      <div class="desc-clamp" style="margin-top: 8px; font-size: 0.8rem; color: #666;">{desc_html}</div>
                    </div>""", unsafe_allow_html=True)
                
                if st.button("＋ Add", key=f"add_pos_{row.id}", use_container_width=True):
                    new_item = {
                        "__id": str(uuid4()), "Description": row.name, "Details": row.description,
                        "Qty": 1, "Price": row.price, "Total": row.price
                    }
                    st.session_state["inv_items"].append(new_item)
                    # Kalau nambah item baru, PDF lama harus dibuang biar regenerate
                    st.session_state["generated_pdf_bytes"] = None 
                    st.toast(f"Ditambahkan: {row.name}", icon="🛒")
                    st.rerun()

# --- KANAN: STRUK (LOGIC DIPERBAIKI) ---
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
                
                c1, c2 = st.columns([3.5, 0.5])
                with c1:
                    st.markdown(f"<div style='font-weight:700; font-size:0.9rem; color:var(--text); margin-bottom:4px;'>{item['Description']}</div>", unsafe_allow_html=True)
                    rc1, rc2 = st.columns([1, 2], vertical_alignment="center")
                    with rc1:
                        new_qty = st.number_input("Qty", min_value=1, value=int(item["Qty"]), key=f"qty_{item['__id']}", label_visibility="collapsed")
                        if new_qty != item["Qty"]:
                            item["Qty"] = new_qty
                            item["Total"] = new_qty * item["Price"]
                            st.session_state["generated_pdf_bytes"] = None # Reset PDF kalau edit qty
                            st.rerun()
                    with rc2: st.caption(f"@ {rupiah(item['Price'])}")

                with c2:
                    if st.button("✕", key=f"del_{item['__id']}", help="Hapus"):
                        st.session_state["inv_items"].pop(i)
                        st.session_state["generated_pdf_bytes"] = None # Reset PDF kalau hapus item
                        st.rerun()
                st.markdown("<div style='border-bottom:1px dashed #eee; margin:8px 0;'></div>", unsafe_allow_html=True)

        # --- CASHBACK & TOTAL ---
        st.write("")
        c_cb_label, c_cb_input = st.columns([2, 1.5], vertical_alignment="center")
        with c_cb_label: st.markdown("<div style='text-align:right; font-weight:600; color:#666;'>Potongan / Cashback (Rp):</div>", unsafe_allow_html=True)
        with c_cb_input:
            new_cb = st.number_input("Cashback", min_value=0, step=10000, key="inv_cashback", label_visibility="collapsed")
        
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
            # 1. Tombol ini HANYA men-trigger pembuatan data PDF, bukan menampilkannya langsung
            if st.button("🚀 PROSES PDF", type="primary", use_container_width=True, disabled=(final_total==0 and subtotal==0)):
                _generate_pdf_state(subtotal, st.session_state["inv_cashback"], final_total, items)
                st.rerun() # Refresh agar UI di bawah muncul

    # --- ACTION AREA (Di Luar Tombol Proses) ---
    # Cek apakah PDF sudah ada di memori session
    if st.session_state.get("generated_pdf_bytes") is not None:
        _render_action_buttons()


# --- FUNGSI BARU: GENERATE STATE ---
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
    
    # Generate dan simpan ke session_state
    pdf_bytes = invoice_mod.generate_pdf_bytes(meta, items, final_total)
    st.session_state["generated_pdf_bytes"] = pdf_bytes
    st.toast("PDF Berhasil dibuat!", icon="✅")

# --- FUNGSI BARU: RENDER ACTION BUTTONS ---
def _render_action_buttons():
    # Ambil data dari state
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
            # Tombol ini sekarang AMAN karena berada di root level, bukan di dalam tombol lain
            if st.button("☁️ Save & Share Email", type="primary", use_container_width=True):
                if not client_email:
                    st.error("⚠️ Masukkan email dulu!")
                else:
                    with st.spinner("Mengupload ke Drive & Mengirim Email..."):
                        # Reset pointer karena mungkin sudah dibaca download button
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

# --- MAIN RENDER ---
def render_page():
    _init_state()
    page_header("Buat Invoice", "Input paket, download atau kirim via email.")
    left, right = st.columns([1.8, 1], gap="medium")
    df = db.load_packages()
    with left: _render_catalog(df)
    with right: 
        _render_receipt()
        st.write("")
        with st.expander("⚙️ Setting Akun Bank"):
            st.text_input("Nama Bank", key="bank_nm")
            st.text_input("No Rekening", key="bank_ac")
            st.text_input("Atas Nama", key="bank_an")