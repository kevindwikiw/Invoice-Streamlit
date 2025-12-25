# modules/db.py
import sqlite3
import streamlit as st
from typing import Optional, List, Dict, Any

DB_NAME = 'packages.db'

# ----------------------------------------------------
# 1. SETUP & INITIALIZATION
# ----------------------------------------------------
def init_db() -> None:
    """
    Initializes the SQLite database with the required schema.
    """
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
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
def load_packages() -> List[Dict[str, Any]]:
    """
    Fetches all packages from the database as a List of Dictionaries.
    Replaces Pandas for better performance and lower RAM usage.
    """
    try:
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            # Mengatur row_factory ke sqlite3.Row agar hasil query bisa diakses seperti Dict
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages")
            rows = cursor.fetchall()
            
            # Konversi hasil ke list of dict biasa
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB ERROR] Load failed: {e}")
        return []

def is_db_empty() -> bool:
    """
    Lightweight check to determine if the database has data.
    """
    try:
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM packages")
            result = cursor.fetchone()
            return result[0] == 0 if result else True
    except Exception:
        return True

# ----------------------------------------------------
# 3. WRITE OPERATIONS (AUTO CLEAR CACHE)
# ----------------------------------------------------
def _clear_cache() -> None:
    """Invalidates the cache to ensure UI reflects latest data."""
    load_packages.clear()

def add_package(name: str, price: float, category: str, description: str) -> None:
    """Inserts a new package record."""
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        c = conn.cursor()
        c.execute(
            'INSERT INTO packages (name, price, category, description) VALUES (?, ?, ?, ?)',
            (name, price, category, description)
        )
        conn.commit()
    _clear_cache()

def update_package(package_id: int, name: str, price: float, category: str, description: str) -> None:
    """Updates an existing package record by ID."""
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE packages
            SET name = ?, price = ?, category = ?, description = ?
            WHERE id = ?
        """, (name, price, category, description, package_id))
        conn.commit()
    _clear_cache()

def delete_package(package_id: int) -> None:
    """Deletes a package record by ID."""
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM packages WHERE id = ?', (package_id,))
        conn.commit()
    _clear_cache()

def delete_all_packages() -> None:
    """Truncates the packages table (Factory Reset)."""
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM packages")
        conn.commit()
    _clear_cache()
