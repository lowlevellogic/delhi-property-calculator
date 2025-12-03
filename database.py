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

    # Users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)

    # OTPs
    c.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );
    """)

    # Colonies
    c.execute("""
        CREATE TABLE IF NOT EXISTS colonies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            colony_name TEXT NOT NULL,
            category TEXT NOT NULL
        );
    """)

    # History
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
        "INSERT INTO colonies (colony_name, category) VALUES (?, ?);", rows
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
