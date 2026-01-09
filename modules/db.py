# modules/db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from typing import Optional, List, Dict, Any

# NOTE: "python-dotenv" is optional if you use Docker (env_file) or Streamlit Cloud (secrets).
# We keep standard os.getenv for flexibility.

# Priority:
# 1. Streamlit Secrets (Deployment)
# 2. Environment Variable (Docker / System)
DATABASE_URL = None
try:
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except (FileNotFoundError, AttributeError):
    pass

if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")

# ----------------------------------------------------
# 1. SETUP & INITIALIZATION
# ----------------------------------------------------
def get_connection():
    if not DATABASE_URL:
        # Stop execution immediately if no DB configured
        st.error("🚨 Configuration Error: `DATABASE_URL` is missing!")
        st.stop()
    return psycopg2.connect(DATABASE_URL)

def init_db() -> None:
    """Initialize Postgres Table (Safe to run multiple times)."""
    if not DATABASE_URL:
        return

    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute('''
                    CREATE TABLE IF NOT EXISTS packages (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        price REAL NOT NULL,
                        category TEXT,
                        description TEXT
                    );
                ''')
            conn.commit()
            print("[DB] Connection successful & Schema verified.")
    except Exception as e:
        st.error(f"❌ Database Connection Failed: {e}")
        # We don't stop here to allow UI to render (maybe showing config help)

# ----------------------------------------------------
# 2. READ OPERATIONS (CACHED)
# ----------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_packages() -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM packages ORDER BY id ASC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception:
        return []

def is_db_empty() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM packages")
                res = cursor.fetchone()
                return res[0] == 0 if res else True
    except Exception:
        return True

# ----------------------------------------------------
# 3. WRITE OPERATIONS
# ----------------------------------------------------
def _clear_cache() -> None:
    load_packages.clear()

def add_package(name: str, price: float, category: str, description: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                'INSERT INTO packages (name, price, category, description) VALUES (%s, %s, %s, %s)',
                (name, price, category, description)
            )
        conn.commit()
    _clear_cache()

def update_package(package_id: int, name: str, price: float, category: str, description: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("""
                UPDATE packages
                SET name = %s, price = %s, category = %s, description = %s
                WHERE id = %s
            """, (name, price, category, description, package_id))
        conn.commit()
    _clear_cache()

def delete_package(package_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute('DELETE FROM packages WHERE id = %s', (package_id,))
        conn.commit()
    _clear_cache()

def delete_all_packages() -> None:
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("TRUNCATE TABLE packages RESTART IDENTITY;")
        conn.commit()
    _clear_cache()
