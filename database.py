import sqlite3
from datetime import datetime, timedelta
import csv
import os

DB_NAME = "data.db"


def get_connection():
    # check_same_thread=False so we can reuse in Streamlit
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ---------- USERS ----------
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)

    # ---------- OTPS ----------
    c.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );
    """)

    # ---------- COLONIES ----------
    c.execute("""
        CREATE TABLE IF NOT EXISTS colonies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            colony_name TEXT NOT NULL,
            category TEXT NOT NULL
        );
    """)

    # ---------- HISTORY (USER-SAVED SUMMARIES) ----------
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            colony_name TEXT,
            property_type TEXT NOT NULL,
            category TEXT NOT NULL,
            consideration REAL NOT NULL,
            stamp_duty REAL NOT NULL,
            e_fees REAL NOT NULL,
            tds REAL NOT NULL,
            total_govt_duty REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ---------- VISITORS (ANONYMOUS OR LOGGED IN) ----------
    # One row per unique visitor_id (session/device)
    c.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT UNIQUE NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            visit_count INTEGER NOT NULL DEFAULT 1,
            device TEXT,
            browser TEXT,
            city TEXT,
            ref_source TEXT
        );
    """)

    # ---------- CALCULATION EVENTS (FOR ANALYTICS) ----------
    # One row per calculation – residential, commercial or DDA
    c.execute("""
        CREATE TABLE IF NOT EXISTS calc_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT,
            user_id INTEGER,
            event_time TEXT NOT NULL,
            property_type TEXT NOT NULL,
            colony_name TEXT,
            category TEXT,
            consideration REAL,
            total_govt_duty REAL,
            device TEXT,
            browser TEXT,
            city TEXT,
            ref_source TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    conn.commit()

    # If colonies table empty -> import from colonies.csv
    c.execute("SELECT COUNT(*) FROM colonies;")
    (count,) = c.fetchone()
    if count == 0:
        import_colonies_from_csv(conn)

    conn.close()


def import_colonies_from_csv(conn=None, csv_path="colonies.csv"):
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    c = conn.cursor()
    if not os.path.exists(csv_path):
        print(f"[database] Warning: {csv_path} not found. Colonies not imported.")
        if close_after:
            conn.close()
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            name = (row.get("colony_name") or row.get("Colony Name") or "").strip()
            cat = (row.get("category") or row.get("Category") or "").strip().upper()
            if name and cat:
                rows.append((name, cat))

    c.execute("DELETE FROM colonies;")
    c.executemany(
        "INSERT INTO colonies (colony_name, category) VALUES (?, ?);",
        rows
    )
    conn.commit()
    print(f"[database] Imported {len(rows)} colonies from {csv_path}.")

    if close_after:
        conn.close()


# ---------- OTP HELPERS ----------

def create_otp(email: str, otp_code: str, minutes_valid: int = 10):
    conn = get_connection()
    c = conn.cursor()
    expires_at = (datetime.utcnow() + timedelta(minutes=minutes_valid)).isoformat()
    c.execute(
        "INSERT INTO otps (email, otp_code, expires_at, used) VALUES (?, ?, ?, 0);",
        (email.lower(), otp_code, expires_at),
    )
    conn.commit()
    conn.close()


def verify_otp(email: str, otp_code: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute(
        """
        SELECT id, expires_at, used FROM otps
        WHERE email = ? AND otp_code = ?
        ORDER BY id DESC LIMIT 1;
        """,
        (email.lower(), otp_code),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    otp_id, expires_at_str, used = row
    if used:
        conn.close()
        return False

    if expires_at_str < now:
        conn.close()
        return False

    # Mark used
    c.execute("UPDATE otps SET used = 1 WHERE id = ?;", (otp_id,))
    conn.commit()
    conn.close()
    return True


# ---------- VISITOR TRACKING HELPERS ----------

def touch_visitor(visitor_id: str,
                  device: str | None = None,
                  browser: str | None = None,
                  city: str | None = None,
                  ref_source: str | None = None):
    """
    Create or update a visitor row.
    Called once per session/run from app.py.
    """
    conn = get_connection()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    # Insert if not exists
    c.execute(
        """
        INSERT OR IGNORE INTO visitors (
            visitor_id, first_seen, last_seen, visit_count, device, browser, city, ref_source
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?);
        """,
        (
            visitor_id,
            now,
            now,
            device,
            browser,
            city,
            ref_source,
        ),
    )

    # If already exists, update last_seen + visit_count + optional fields
    c.execute(
        """
        UPDATE visitors
        SET last_seen = ?,
            visit_count = visit_count + 1,
            device = COALESCE(?, device),
            browser = COALESCE(?, browser),
            city = COALESCE(?, city),
            ref_source = COALESCE(?, ref_source)
        WHERE visitor_id = ?;
        """,
        (now, device, browser, city, ref_source, visitor_id),
    )

    conn.commit()
    conn.close()


def log_calc_event(
    visitor_id: str | None,
    user_id: int | None,
    property_type: str,
    colony_name: str | None,
    category: str | None,
    consideration: float | None,
    total_govt_duty: float | None,
    device: str | None = None,
    browser: str | None = None,
    city: str | None = None,
    ref_source: str | None = None,
):
    """
    Log one calculation (res/com/DDA) for analytics.
    Can be called for anonymous or logged-in users.
    """
    conn = get_connection()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    c.execute(
        """
        INSERT INTO calc_events (
            visitor_id, user_id, event_time,
            property_type, colony_name, category,
            consideration, total_govt_duty,
            device, browser, city, ref_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            visitor_id,
            user_id,
            now,
            property_type,
            colony_name,
            category,
            consideration,
            total_govt_duty,
            device,
            browser,
            city,
            ref_source,
        ),
    )

    conn.commit()
    conn.close()
