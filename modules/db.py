# modules/db.py
import os
import sqlite3
import streamlit as st
import json
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

# --- Optional Postgres Support ---
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


# --- Environment Loading ---
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


# --- Database Configuration ---
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

USE_POSTGRES = bool(DATABASE_URL) and HAS_PSYCOPG2
DB_SQLITE = 'packages.db'


# --- Adapter Interface ---
class DatabaseAdapter(ABC):
    """Abstract Base Class for Database Interactions."""
    
    @abstractmethod
    def init_db(self) -> None:
        pass
    
    @abstractmethod
    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        pass
        
    @abstractmethod
    def set_config(self, key: str, value: str) -> None:
        pass
        
    @abstractmethod
    def save_invoice(self, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str) -> None:
        pass
        
    @abstractmethod
    def get_invoices(self, limit: int = 50) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def search_invoices(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def get_invoice_details(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def update_invoice(self, invoice_id: int, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str) -> None:
        pass
        
    @abstractmethod
    def delete_invoice(self, invoice_id: int) -> None:
        pass
    
    @abstractmethod
    def get_dashboard_stats(self) -> Dict[str, Any]:
        pass

    # Package Management
    @abstractmethod
    def load_packages(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def add_package(self, name: str, price: float, category: str, description: str) -> None:
        pass

    @abstractmethod
    def update_package(self, package_id: int, name: str, price: float, category: str, description: str) -> None:
        pass

    @abstractmethod
    def delete_package(self, package_id: int) -> None:
        pass
        
    @abstractmethod
    def delete_all_packages(self) -> None:
        pass
        
    @abstractmethod
    def is_db_empty(self) -> bool:
        pass

    @abstractmethod
    def get_analytics_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Returns {count, revenue} for specific month."""
        pass

    @abstractmethod
    def get_analytics_revenue_trend(self, year: int) -> List[Dict[str, Any]]:
        """Returns monthly revenue for the year."""
        pass

    @abstractmethod
    def get_analytics_top_packages(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns most popular packages based on saved invoice data."""
        pass

    @abstractmethod
    def get_monthly_report_data(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Returns list of invoices for tabular report."""
        pass

    @abstractmethod
    def get_yearly_report_data(self, year: int) -> List[Dict[str, Any]]:
        """Returns list of invoices for yearly tabular report."""
        pass


# --- SQLite Implementation ---
class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            # Packages
            c.execute('''
                CREATE TABLE IF NOT EXISTS packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    category TEXT,
                    description TEXT
                )
            ''')
            # Config
            c.execute('''
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Invoices
            c.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_no TEXT,
                    client_name TEXT,
                    date TEXT,
                    total_amount REAL,
                    invoice_data TEXT,
                    pdf_blob BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Migration: Add pdf_blob column if missing (for existing DBs)
            try:
                c.execute("ALTER TABLE invoices ADD COLUMN pdf_blob BLOB")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Migration: Add is_active column for Package Archiving
            try:
                c.execute("ALTER TABLE packages ADD COLUMN is_active INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass 
                
            conn.commit()

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM app_config WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row['value'] if row else default
        except Exception as e:
            print(f"[SQLite] get_config failed: {e}")
            return default

    def set_config(self, key: str, value: str) -> None:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, value))
                conn.commit()
        except Exception as e:
            print(f"[SQLite] set_config failed: {e}")

    def save_invoice(self, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str, pdf_blob: bytes = None) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute("""
            INSERT INTO invoices (invoice_no, client_name, date, total_amount, invoice_data, pdf_blob)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_no, client_name, date_str, total_amount, invoice_data_json, pdf_blob))
            conn.commit()
        # Invalidate analytics cache
        bump_analytics_version()

    def get_invoices(self, limit: int = 50) -> List[Dict[str, Any]]:
        # Using json_extract for client_phone
        query = """
            SELECT id, invoice_no, client_name, date, total_amount, created_at, 
                   LENGTH(invoice_data) as data_size,
                   json_extract(invoice_data, '$.meta.client_phone') as client_phone,
                   json_extract(invoice_data, '$.meta.wedding_date') as wedding_date,
                   json_extract(invoice_data, '$.meta.payment_terms') as payment_terms
            FROM invoices ORDER BY id DESC LIMIT ?
        """
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query, (limit,))
                return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[SQLite] get_invoices failed: {e}")
            return []

    def search_invoices(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        # Using simple LIKE search
        sql = """
            SELECT id, invoice_no, client_name, date, total_amount, created_at, 
                   LENGTH(invoice_data) as data_size,
                   json_extract(invoice_data, '$.meta.client_phone') as client_phone,
                   json_extract(invoice_data, '$.meta.wedding_date') as wedding_date,
                   json_extract(invoice_data, '$.meta.payment_terms') as payment_terms
            FROM invoices 
            WHERE invoice_no LIKE ? OR client_name LIKE ?
            ORDER BY id DESC LIMIT ?
        """
        wild = f"%{query}%"
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(sql, (wild, wild, limit))
                return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[SQLite] search_invoices failed: {e}")
            return []

    def get_invoice_details(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
                row = c.fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def update_invoice(self, invoice_id: int, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str, pdf_blob: bytes = None) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE invoices
                SET invoice_no=?, client_name=?, date=?, total_amount=?, invoice_data=?, pdf_blob=?
                WHERE id=?
            """, (invoice_no, client_name, date_str, total_amount, invoice_data_json, pdf_blob, invoice_id))
            conn.commit()
        # Invalidate analytics cache
        bump_analytics_version()

    def delete_invoice(self, invoice_id: int) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            conn.commit()
        # Invalidate analytics cache
        bump_analytics_version()

    def get_dashboard_stats(self) -> Dict[str, Any]:
        query = "SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue FROM invoices"
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query)
                row = c.fetchone()
                return dict(row) if row else {"count": 0, "revenue": 0}
        except Exception:
            return {"count": 0, "revenue": 0}

    def get_analytics_summary(self, year: int, month: int) -> Dict[str, Any]:
        # Date format assumed YYYY-MM-DD
        pattern = f"{year}-{month:02d}-%"
        query = "SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue FROM invoices WHERE date LIKE ?"
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query, (pattern,))
                row = c.fetchone()
                return dict(row) if row else {"count": 0, "revenue": 0}
        except Exception:
            return {"count": 0, "revenue": 0}

    def get_analytics_revenue_trend(self, year: int) -> List[Dict[str, Any]]:
        # Returns list of {month: 1-12, revenue: float}
        pattern = f"{year}-%"
        # Extract month from YYYY-MM-DD (substr(date, 6, 2))
        query = """
            SELECT substr(date, 6, 2) as month, SUM(total_amount) as revenue 
            FROM invoices 
            WHERE date LIKE ? 
            GROUP BY month 
            ORDER BY month
        """
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query, (pattern,))
                return [{"month": int(r["month"]), "revenue": r["revenue"]} for r in c.fetchall()]
        except Exception:
            return []

    def get_analytics_top_packages(self, limit: int = 5) -> List[Dict[str, Any]]:
        # Fetches all invoice_data and counts in Python (hard to do robustly in SQLite JSON)
        query = "SELECT invoice_data FROM invoices ORDER BY id DESC LIMIT 200" # Limit analysis to last 200 for perf
        package_counts = {}
        
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query)
                rows = c.fetchall()
                
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    items = data.get("items", [])
                    for item in items:
                        name = item.get("Description", "Unknown")
                        qty = item.get("Qty", 1)
                        if name in package_counts:
                            package_counts[name] += qty
                        else:
                            package_counts[name] = qty
                except:
                    continue
            
            # Sort top N
            sorted_pkg = sorted(package_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return [{"name": k, "count": v} for k, v in sorted_pkg]
            
        except Exception:
            return []

    def get_analytics_bookings(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = "SELECT id, invoice_no, client_name, total_amount, invoice_data FROM invoices ORDER BY date DESC LIMIT ?"
        bookings = []
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query, (limit,))
                rows = c.fetchall()
            
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    meta = data.get("meta", {})
                    
                    # Extract fields
                    w_date = meta.get("wedding_date", "")
                    venue = meta.get("venue", "Unknown Venue")
                    title = meta.get("title", f"Invoice #{r['invoice_no']}")
                    
                    bookings.append({
                        "id": r['id'],
                        "date": w_date,
                        "venue": venue,
                        "client": r['client_name'],
                        "title": title,
                        "amount": r['total_amount'],
                        "items": data.get("items", [])
                    })
                except:
                    continue
            return bookings
        except Exception:
            return []

    def get_monthly_report_data(self, year: int, month: int) -> List[Dict[str, Any]]:
        pattern = f"{year}-{month:02d}-%"
        query = "SELECT id, invoice_no, client_name, date, total_amount, invoice_data FROM invoices WHERE date LIKE ? ORDER BY date ASC"
        result = []
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query, (pattern,))
                rows = c.fetchall()
            
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    meta = data.get("meta", {})
                    result.append({
                        "id": r['id'],
                        "invoice_no": r['invoice_no'],
                        "client": r['client_name'],
                        "created_date": r['date'],
                        "event_date": w_date,
                        "venue": venue,
                        "amount": r['total_amount'],
                        "meta": meta
                    })
                except:
                    continue
            return result
        except Exception:
            return []

    def get_yearly_report_data(self, year: int) -> List[Dict[str, Any]]:
        pattern = f"{year}-%"
        query = "SELECT id, invoice_no, client_name, date, total_amount, invoice_data FROM invoices WHERE date LIKE ? ORDER BY date ASC"
        result = []
        try:
            with self._connect() as conn:
                c = conn.cursor()
                c.execute(query, (pattern,))
                rows = c.fetchall()
            
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    meta = data.get("meta", {})
                    result.append({
                        "id": r['id'],
                        "invoice_no": r['invoice_no'],
                        "client": r['client_name'],
                        "created_date": r['date'],
                        "event_date": meta.get("wedding_date", ""),
                        "venue": meta.get("venue", "Unknown"),
                        "amount": r['total_amount'],
                        "meta": meta
                    })
                except:
                    continue
            return result
        except Exception:
            return []

    def load_packages(self, active_only: bool = True) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                if active_only:
                    cursor.execute("SELECT * FROM packages WHERE is_active = 1")
                else:
                    cursor.execute("SELECT * FROM packages")
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def add_package(self, name: str, price: float, category: str, description: str) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO packages (name, price, category, description) VALUES (?, ?, ?, ?)',
                (name, price, category, description)
            )
            conn.commit()
        bump_package_version()

    def update_package(self, package_id: int, name: str, price: float, category: str, description: str) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE packages
                SET name = ?, price = ?, category = ?, description = ?
                WHERE id = ?
            """, (name, price, category, description, package_id))
            conn.commit()
        bump_package_version()

    def delete_package(self, package_id: int) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM packages WHERE id = ?', (package_id,))
            conn.commit()
        bump_package_version()

    def toggle_package_status(self, package_id: int, is_active: bool) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            val = 1 if is_active else 0
            c.execute("UPDATE packages SET is_active = ? WHERE id = ?", (val, package_id))
            conn.commit()
        bump_package_version()

    def delete_all_packages(self) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM packages")
            conn.commit()

    def is_db_empty(self) -> bool:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM packages")
                res = cursor.fetchone()
                return res[0] == 0 if res else True
        except Exception:
            return True


# --- Postgres Implementation ---
class PostgresAdapter(DatabaseAdapter):
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        return psycopg2.connect(self.dsn)

    def init_db(self) -> None:
        try:
            with self._connect() as conn:
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
                    c.execute('''
                        CREATE TABLE IF NOT EXISTS app_config (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        );
                    ''')
                    c.execute('''
                        CREATE TABLE IF NOT EXISTS invoices (
                            id SERIAL PRIMARY KEY,
                            invoice_no TEXT,
                            client_name TEXT,
                            date TEXT,
                            total_amount REAL,
                            invoice_data TEXT,
                            pdf_blob BYTEA,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    ''')
                    # Migration: Add pdf_blob column if missing
                    try:
                        c.execute("ALTER TABLE invoices ADD COLUMN pdf_blob BYTEA")
                    except Exception:
                        pass  # Column likely exists
                conn.commit()
                print("[DB] Postgres Schema initialized.")
        except Exception as e:
            print(f"[Postgres] Init failed: {e}")

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT value FROM app_config WHERE key = %s", (key,))
                    row = cursor.fetchone()
                    return row[0] if row else default
        except Exception as e:
            print(f"[Postgres] get_config failed: {e}")
            return default

    def set_config(self, key: str, value: str) -> None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO app_config (key, value) VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                    """, (key, value))
                conn.commit()
        except Exception as e:
            print(f"[Postgres] set_config failed: {e}")

    def save_invoice(self, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str, pdf_blob: bytes = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO invoices (invoice_no, client_name, date, total_amount, invoice_data, pdf_blob)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (invoice_no, client_name, date_str, total_amount, invoice_data_json, pdf_blob))
            conn.commit()

    def get_invoices(self, limit: int = 50) -> List[Dict[str, Any]]:
        query = """
            SELECT id, invoice_no, client_name, date, total_amount, created_at, 
                   LENGTH(invoice_data) as data_size,
                   invoice_data::json->'meta'->>'client_phone' as client_phone,
                   invoice_data::json->'meta'->>'wedding_date' as wedding_date,
                   invoice_data::json->'meta'->'payment_terms' as payment_terms
            FROM invoices ORDER BY id DESC LIMIT %s
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (limit,))
                    return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[Postgres] get_invoices failed: {e}")
            return []

    def search_invoices(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, invoice_no, client_name, date, total_amount, created_at, 
                   LENGTH(invoice_data) as data_size,
                   invoice_data::json->'meta'->>'client_phone' as client_phone,
                   invoice_data::json->'meta'->>'wedding_date' as wedding_date,
                   invoice_data::json->'meta'->'payment_terms' as payment_terms
            FROM invoices 
            WHERE invoice_no ILIKE %s OR client_name ILIKE %s
            ORDER BY id DESC LIMIT %s
        """
        wild = f"%{query}%"
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(sql, (wild, wild, limit))
                    return [dict(row) for row in c.fetchall()]
        except Exception as e:
            print(f"[Postgres] search_invoices failed: {e}")
            return []

    def get_invoice_details(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
                    row = c.fetchone()
                    return dict(row) if row else None
        except Exception:
            return None

    def update_invoice(self, invoice_id: int, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str, pdf_blob: bytes = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE invoices 
                    SET invoice_no=%s, client_name=%s, date=%s, total_amount=%s, invoice_data=%s, pdf_blob=%s
                    WHERE id=%s
                """, (invoice_no, client_name, date_str, total_amount, invoice_data_json, pdf_blob, invoice_id))
            conn.commit()

    def delete_invoice(self, invoice_id: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute('DELETE FROM invoices WHERE id = %s', (invoice_id,))
            conn.commit()

    def get_dashboard_stats(self) -> Dict[str, Any]:
        query = "SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue FROM invoices"
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query)
                    row = c.fetchone()
                    return dict(row) if row else {"count": 0, "revenue": 0}
        except Exception:
            return {"count": 0, "revenue": 0}

    def load_packages(self) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT * FROM packages ORDER BY id ASC")
                    return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def add_package(self, name: str, price: float, category: str, description: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute(
                    'INSERT INTO packages (name, price, category, description) VALUES (%s, %s, %s, %s)',
                    (name, price, category, description)
                )
            conn.commit()

    def update_package(self, package_id: int, name: str, price: float, category: str, description: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE packages
                    SET name = %s, price = %s, category = %s, description = %s
                    WHERE id = %s
                """, (name, price, category, description, package_id))
            conn.commit()

    def delete_package(self, package_id: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute('DELETE FROM packages WHERE id = %s', (package_id,))
            conn.commit()

    def delete_all_packages(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as c:
                c.execute("TRUNCATE TABLE packages RESTART IDENTITY;")
            conn.commit()

    def is_db_empty(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM packages")
                    res = cursor.fetchone()
                    return res[0] == 0 if res else True
        except Exception:
            return True

    def get_analytics_summary(self, year: int, month: int) -> Dict[str, Any]:
        pattern = f"{year}-{month:02d}-%"
        query = "SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue FROM invoices WHERE date LIKE %s"
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (pattern,))
                    row = c.fetchone()
                    return dict(row) if row else {"count": 0, "revenue": 0}
        except Exception:
            return {"count": 0, "revenue": 0}

    def get_analytics_revenue_trend(self, year: int) -> List[Dict[str, Any]]:
        pattern = f"{year}-%"
        # Extract month from YYYY-MM-DD
        query = """
            SELECT substring(date, 6, 2) as month, SUM(total_amount) as revenue 
            FROM invoices 
            WHERE date LIKE %s 
            GROUP BY month 
            ORDER BY month
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (pattern,))
                    return [{"month": int(r["month"]), "revenue": r["revenue"]} for r in c.fetchall()]
        except Exception:
            return []

    def get_analytics_top_packages(self, limit: int = 5) -> List[Dict[str, Any]]:
        # Postgres can do JSONB aggregation better, but sticking to Python for consistency with SQLite logic
        query = "SELECT invoice_data FROM invoices ORDER BY id DESC LIMIT 200"
        package_counts = {}
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query)
                    rows = c.fetchall()
            
            for r in rows:
                try:
                    # invoice_data is already string in this schema text
                    data = json.loads(r["invoice_data"])
                    items = data.get("items", [])
                    for item in items:
                        name = item.get("Description", "Unknown")
                        qty = item.get("Qty", 1)
                        if name in package_counts:
                            package_counts[name] += qty
                        else:
                            package_counts[name] = qty
                except:
                    continue
            
            sorted_pkg = sorted(package_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return [{"name": k, "count": v} for k, v in sorted_pkg]
        except Exception:
            return []

    def get_analytics_bookings(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = "SELECT id, invoice_no, client_name, total_amount, invoice_data FROM invoices ORDER BY date DESC LIMIT %s"
        bookings = []
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (limit,))
                    rows = c.fetchall()
            
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    meta = data.get("meta", {})
                    
                    bookings.append({
                        "id": r['id'],
                        "date": meta.get("wedding_date", ""),
                        "venue": meta.get("venue", "Unknown Venue"),
                        "client": r['client_name'],
                        "title": meta.get("title", f"Invoice #{r['invoice_no']}"),
                        "amount": r['total_amount'],
                        "items": data.get("items", [])
                    })
                except:
                    continue
            return bookings
        except Exception:
            return []

    def get_monthly_report_data(self, year: int, month: int) -> List[Dict[str, Any]]:
        pattern = f"{year}-{month:02d}-%"
        query = "SELECT id, invoice_no, client_name, date, total_amount, invoice_data FROM invoices WHERE date LIKE %s ORDER BY date ASC"
        result = []
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (pattern,))
                    rows = c.fetchall()
            
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    meta = data.get("meta", {})
                    
                    result.append({
                        "id": r['id'],
                        "invoice_no": r['invoice_no'],
                        "client": r['client_name'],
                        "created_date": r['date'],
                        "event_date": meta.get("wedding_date", ""),
                        "venue": meta.get("venue", "Unknown"),
                        "amount": r['total_amount'],
                        "meta": meta
                    })
                except:
                    continue
            return result
        except Exception:
            return []

    def get_yearly_report_data(self, year: int) -> List[Dict[str, Any]]:
        pattern = f"{year}-%"
        query = "SELECT id, invoice_no, client_name, date, total_amount, invoice_data FROM invoices WHERE date LIKE %s ORDER BY date ASC"
        result = []
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as c:
                    c.execute(query, (pattern,))
                    rows = c.fetchall()
            
            for r in rows:
                try:
                    data = json.loads(r["invoice_data"])
                    meta = data.get("meta", {})
                    result.append({
                        "id": r['id'],
                        "invoice_no": r['invoice_no'],
                        "client": r['client_name'],
                        "created_date": r['date'],
                        "event_date": meta.get("wedding_date", ""),
                        "venue": meta.get("venue", "Unknown"),
                        "amount": r['total_amount'],
                        "meta": meta
                    })
                except:
                    continue
            return result
        except Exception:
            return []


# --- Factory & Singleton ---
if USE_POSTGRES:
    current_db = PostgresAdapter(DATABASE_URL)
else:
    current_db = SQLiteAdapter(DB_SQLITE)


# --- Public API (Proxies) ---
_db_schema_initialized = False  # Module-level flag to prevent redundant CREATE TABLE calls

def init_db() -> None:
    global _db_schema_initialized
    if _db_schema_initialized:
        return  # Skip if already initialized in this process
    current_db.init_db()
    _db_schema_initialized = True

def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    return current_db.get_config(key, default)

def set_config(key: str, value: str) -> None:
    current_db.set_config(key, value)

def save_invoice(invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str, pdf_blob: bytes = None) -> None:
    current_db.save_invoice(invoice_no, client_name, date_str, total_amount, invoice_data_json, pdf_blob)
    bump_analytics_version()

def get_invoices(limit: int = 50) -> List[Dict[str, Any]]:
    return current_db.get_invoices(limit)

def get_invoice_details(invoice_id: int) -> Optional[Dict[str, Any]]:
    return current_db.get_invoice_details(invoice_id)

def update_invoice(invoice_id: int, invoice_no: str, client_name: str, date_str: str, total_amount: float, invoice_data_json: str, pdf_blob: bytes = None) -> None:
    current_db.update_invoice(invoice_id, invoice_no, client_name, date_str, total_amount, invoice_data_json, pdf_blob)
    bump_analytics_version()

def delete_invoice(invoice_id: int) -> None:
    current_db.delete_invoice(invoice_id)
    bump_analytics_version()

def get_dashboard_stats() -> Dict[str, Any]:
    return current_db.get_dashboard_stats()

def get_analytics_summary(year: int, month: int) -> Dict[str, Any]:
    return current_db.get_analytics_summary(year, month)

def get_analytics_revenue_trend(year: int) -> List[Dict[str, Any]]:
    return current_db.get_analytics_revenue_trend(year)

def get_analytics_top_packages(limit: int = 5) -> List[Dict[str, Any]]:
    return current_db.get_analytics_top_packages(limit)

def get_analytics_bookings(limit: int = 20) -> List[Dict[str, Any]]:
    return current_db.get_analytics_bookings(limit)

def get_monthly_report_data(year: int, month: int) -> List[Dict[str, Any]]:
    return current_db.get_monthly_report_data(year, month)

def get_yearly_report_data(year: int) -> List[Dict[str, Any]]:
    return current_db.get_yearly_report_data(year)

# Cached Wrapper for Load Packages
@st.cache_data(ttl=300, show_spinner=False)
def load_packages(active_only: bool = True) -> List[Dict[str, Any]]:
    return current_db.load_packages(active_only=active_only)

def _clear_cache() -> None:
    load_packages.clear()

def add_package(name: str, price: float, category: str, description: str) -> None:
    current_db.add_package(name, price, category, description)
    _clear_cache()

def update_package(package_id: int, name: str, price: float, category: str, description: str) -> None:
    current_db.update_package(package_id, name, price, category, description)
    _clear_cache()

def delete_package(package_id: int) -> None:
    current_db.delete_package(package_id)
    _clear_cache()

def toggle_package_status(package_id: int, is_active: bool) -> None:
    if hasattr(current_db, 'toggle_package_status'):
        current_db.toggle_package_status(package_id, is_active)
        _clear_cache()

def delete_all_packages() -> None:
    current_db.delete_all_packages()
    _clear_cache()

def is_db_empty() -> bool:
    return current_db.is_db_empty()

# --- Versioning for Smart Caching ---
def get_package_version() -> str:
    """Returns the current package database version (timestamp)."""
    return get_config("package_version", "0")

def bump_package_version() -> None:
    """Updates the package database version to current timestamp."""
    import time
    set_config("package_version", str(time.time()))

def get_next_invoice_seq(prefix: str) -> int:
    """
    Get and increment invoice sequence for a given client prefix.
    Stores in app_config with key 'inv_seq_{PREFIX}'.
    Returns the NEXT sequence number (already incremented).
    """
    config_key = f"inv_seq_{prefix}"
    
    # Get current value (calls adapter)
    current = get_config(config_key, "0")
    try:
        current_seq = int(current)
    except:
        current_seq = 0
    
    # Increment
    next_seq = current_seq + 1
    
    # Save back (calls adapter)
    set_config(config_key, str(next_seq))
    
    return next_seq

# Global sequence for Auto-Gen (INV00001)
def peek_next_global_sequence() -> int:
    """Gets the next global sequence number WITHOUT incrementing it yet."""
    config_key = "inv_seq_global"
    current = get_config(config_key, "0")
    try:
        current_seq = int(current)
    except:
        current_seq = 0
    return current_seq + 1

def update_global_sequence_if_needed(used_seq: int) -> None:
    """Updates the global sequence if the used_seq > current stored sequence."""
    config_key = "inv_seq_global"
    current = get_config(config_key, "0")
    try:
        current_seq = int(current)
    except:
        current_seq = 0
    
    if used_seq > current_seq:
        set_config(config_key, str(used_seq))

def get_next_global_sequence() -> int:
    """Gets the next global sequence number (inv_seq_global) AND increments it."""
    return get_next_invoice_seq("global")  # Re-use existing logic with 'global' prefix

# --- Smart Caching Helpers (Analytics) ---
def get_analytics_version() -> str:
    """Returns a timestamp of the last invoice update (affects analytics)."""
    return get_config('analytics_version', default='0')

def bump_analytics_version() -> None:
    """Updates the analytics version timestamp to now."""
    import time
    set_config('analytics_version', str(time.time()))
