# modules/db.py
import os
import sqlite3
import streamlit as st
from typing import Optional, List, Dict, Any

# Try to import psycopg2 for Postgres
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Load .env locally (Manual implementation to save dependency)
def _load_env_file():
    try:
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())
    except:
        pass

_load_env_file()

# Priority:
# 1. Streamlit Secrets (Deployment)
# 2. Environment Variable (.env)
DATABASE_URL = None
try:
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except (FileNotFoundError, AttributeError):
    pass

if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")

# --- MODE DETECTION ---
# If DATABASE_URL is present -> Postgres Mode
# If None -> SQLite Mode
USE_POSTGRES = bool(DATABASE_URL) and HAS_PSYCOPG2

DB_SQLITE = 'packages.db'

# ----------------------------------------------------
# 1. SETUP & INITIALIZATION
# ----------------------------------------------------
def get_pg_connection():
    if not USE_POSTGRES:
        raise ValueError("Not in Postgres Mode.")
    return psycopg2.connect(DATABASE_URL)

def init_db() -> None:
    """Initialize DB Schema (SQLite or Postgres)."""
    if USE_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite()

# ... existing code ...

# ... (previous code) ...

def _init_sqlite():
    with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
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
        # Config Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Invoices History Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT,
                client_name TEXT,
                date TEXT,
                total_amount REAL,
                invoice_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def _init_postgres():
    try:
        with get_pg_connection() as conn:
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
                # Config Table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS app_config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                ''')
                # Invoices History Table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS invoices (
                        id SERIAL PRIMARY KEY,
                        invoice_no TEXT,
                        client_name TEXT,
                        date TEXT,
                        total_amount REAL,
                        invoice_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
            conn.commit()
            print("[DB] Postgres Schema initialized.")
    except Exception as e:
        print(f"[DB ERROR] Postgres Init failed: {e}")

# ... (existing config functions) ...

# ----------------------------------------------------
# 5. INVOICE HISTORY OPERATIONS
# ----------------------------------------------------
def save_invoice(invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str) -> None:
    """Saves an invoice snapshot to history."""
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO invoices (invoice_no, client_name, date, total_amount, invoice_data)
                    VALUES (%s, %s, %s, %s, %s)
                """, (invoice_no, client_name, date_str, total_amount, invoice_data_json))
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO invoices (invoice_no, client_name, date, total_amount, invoice_data)
                VALUES (?, ?, ?, ?, ?)
            """, (invoice_no, client_name, date_str, total_amount, invoice_data_json))
            conn.commit()

def get_invoices(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches recent invoices list (metadata only)."""
    # We fetch LENGTH(invoice_data) to guess if an image is attached (heuristically > 10KB)
    query = "SELECT id, invoice_no, client_name, date, total_amount, created_at, LENGTH(invoice_data) as data_size FROM invoices ORDER BY id DESC LIMIT %s"
    
    if USE_POSTGRES:
        try:
            with get_pg_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (limit,))
                    return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_invoices failed: {e}")
            return []
    else:
        try:
            with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query.replace("%s", "?"), (limit,))
                return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[DB ERROR] get_invoices failed: {e}")
            return []

def get_invoice_details(invoice_id: int) -> Optional[Dict[str, Any]]:
    """Fetches full invoice data (including JSON snapshot)."""
    query = "SELECT * FROM invoices WHERE id = %s"
    if USE_POSTGRES:
        try:
            with get_pg_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (invoice_id,))
                    row = c.fetchone()
                    return dict(row) if row else None
        except Exception:
            return None
    else:
        try:
            with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query.replace("%s", "?"), (invoice_id,))
                row = c.fetchone()
                return dict(row) if row else None
        except Exception:
            return None

def delete_invoice(invoice_id: int) -> None:
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute('DELETE FROM invoices WHERE id = %s', (invoice_id,))
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
            conn.commit()

def update_invoice(invoice_id: int, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str) -> None:
    """Updates an existing invoice."""
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE invoices 
                    SET invoice_no=%s, client_name=%s, date=%s, total_amount=%s, invoice_data=%s
                    WHERE id=%s
                """, (invoice_no, client_name, date_str, total_amount, invoice_data_json, invoice_id))
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE invoices
                SET invoice_no=?, client_name=?, date=?, total_amount=?, invoice_data=?
                WHERE id=?
            """, (invoice_no, client_name, date_str, total_amount, invoice_data_json, invoice_id))
            conn.commit()

def get_dashboard_stats() -> Dict[str, Any]:
    """Returns quick dashboard stats: Total Revenue, Invoice Count."""
    query = "SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue FROM invoices"
    
    try:
        if USE_POSTGRES:
            with get_pg_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query)
                    return dict(c.fetchone())
        else:
            with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(query)
                return dict(c.fetchone())
    except Exception as e:
        print(f"Stats Error: {e}")
        return {"count": 0, "revenue": 0}

# ... existing code ...

# ----------------------------------------------------
# 4. CONFIGURATION (Persistent Settings)
# ----------------------------------------------------
def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch a setting value by key."""
    query = "SELECT value FROM app_config WHERE key = %s" if USE_POSTGRES else "SELECT value FROM app_config WHERE key = ?"
    
    try:
        conn_ctx = get_pg_connection() if USE_POSTGRES else sqlite3.connect(DB_SQLITE, timeout=10)
        with conn_ctx as conn:
            cursor = conn.cursor()
            cursor.execute(query, (key,))
            row = cursor.fetchone()
            return row[0] if row else default
    except Exception as e:
        print(f"[DB ERROR] get_config failed: {e}")
        return default

def set_config(key: str, value: str) -> None:
    """Upsert a setting value."""
    if USE_POSTGRES:
        query = """
            INSERT INTO app_config (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """
        conn_ctx = get_pg_connection()
    else:
        query = """
            INSERT INTO app_config (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = expected.value;
        """ 
        # SQLite ON CONFLICT syntax is slightly different or standard. 
        # Standard: INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)
        query = "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)"
        conn_ctx = sqlite3.connect(DB_SQLITE, timeout=10)

    try:
        with conn_ctx as conn:
            cursor = conn.cursor()
            cursor.execute(query, (key, value))
        conn.commit()
    except Exception as e:
        print(f"[DB ERROR] set_config failed: {e}")

def get_next_invoice_seq(prefix: str) -> int:
    """
    Get and increment invoice sequence for a given client prefix.
    Stores in app_config with key 'inv_seq_{PREFIX}'.
    Returns the NEXT sequence number (already incremented).
    """
    config_key = f"inv_seq_{prefix}"
    
    # Get current value
    current = get_config(config_key, "0")
    try:
        current_seq = int(current)
    except:
        current_seq = 0
    
    # Increment
    next_seq = current_seq + 1
    
    # Save back
    set_config(config_key, str(next_seq))
    
    return next_seq


# ----------------------------------------------------
# 2. READ OPERATIONS (CACHED)
# ----------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_packages() -> List[Dict[str, Any]]:
    if USE_POSTGRES:
        return _load_postgres()
    return _load_sqlite()

def _load_sqlite() -> List[Dict[str, Any]]:
    try:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB ERROR] SQLite Load failed: {e}")
        return []

def _load_postgres() -> List[Dict[str, Any]]:
    try:
        with get_pg_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM packages ORDER BY id ASC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB ERROR] Postgres Load failed: {e}")
        return []

def is_db_empty() -> bool:
    if USE_POSTGRES:
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM packages")
                    res = cursor.fetchone()
                    return res[0] == 0 if res else True
        except Exception:
            return True
    else:
        try:
            with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM packages")
                res = cursor.fetchone()
                return res[0] == 0 if res else True
        except Exception:
            return True

# ----------------------------------------------------
# 3. WRITE OPERATIONS (AUTO CLEAR CACHE)
# ----------------------------------------------------
def _clear_cache() -> None:
    load_packages.clear()

def add_package(name: str, price: float, category: str, description: str) -> None:
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute(
                    'INSERT INTO packages (name, price, category, description) VALUES (%s, %s, %s, %s)',
                    (name, price, category, description)
                )
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO packages (name, price, category, description) VALUES (?, ?, ?, ?)',
                (name, price, category, description)
            )
            conn.commit()
    _clear_cache()

def update_package(package_id: int, name: str, price: float, category: str, description: str) -> None:
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE packages
                    SET name = %s, price = %s, category = %s, description = %s
                    WHERE id = %s
                """, (name, price, category, description, package_id))
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE packages
                SET name = ?, price = ?, category = ?, description = ?
                WHERE id = ?
            """, (name, price, category, description, package_id))
            conn.commit()
    _clear_cache()

def delete_package(package_id: int) -> None:
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute('DELETE FROM packages WHERE id = %s', (package_id,))
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM packages WHERE id = ?', (package_id,))
            conn.commit()
    _clear_cache()

def delete_all_packages() -> None:
    if USE_POSTGRES:
        with get_pg_connection() as conn:
            with conn.cursor() as c:
                c.execute("TRUNCATE TABLE packages RESTART IDENTITY;")
            conn.commit()
    else:
        with sqlite3.connect(DB_SQLITE, timeout=10) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM packages")
            conn.commit()
    _clear_cache()
