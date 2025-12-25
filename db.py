import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = 'packages.db'

# ----------------------------------------------------
# 1. SETUP & INIT
# ----------------------------------------------------
def init_db():
    """Membuat tabel jika belum ada. Aman dipanggil berulang kali."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                description TEXT
            )
        ''')
        conn.commit()

# ----------------------------------------------------
# 2. READ OPERATIONS (CACHED)
# ----------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_packages():
    """Load semua data dengan cache biar ringan."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return pd.read_sql_query("SELECT * FROM packages", conn)
    except Exception:
        return pd.DataFrame()

def is_db_empty():
    """Cek cepat tanpa load seluruh data (Hemat RAM)."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM packages")
            return cursor.fetchone()[0] == 0
    except Exception:
        return True

# ----------------------------------------------------
# 3. WRITE OPERATIONS (AUTO CLEAR CACHE)
# ----------------------------------------------------
def _clear_cache():
    """Hapus cache agar tabel UI update realtime."""
    load_packages.clear()

def add_package(name, price, category, description):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO packages (name, price, category, description) VALUES (?, ?, ?, ?)',
                  (name, price, category, description))
        conn.commit()
    _clear_cache()

def update_package(package_id, name, price, category, description):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE packages
            SET name = ?, price = ?, category = ?, description = ?
            WHERE id = ?
        """, (name, price, category, description, package_id))
        conn.commit()
    _clear_cache()

def delete_package(package_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM packages WHERE id = ?', (package_id,))
        conn.commit()
    _clear_cache()

def delete_all_packages():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM packages")
        conn.commit()
    _clear_cache()