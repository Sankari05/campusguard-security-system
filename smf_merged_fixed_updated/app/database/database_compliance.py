# =============================================================
# database_compliance.py — NEW FILE (additive only)
#
# Tracks NBA/NAAC accreditation document deadlines and status.
# Completely new, independent table.
# =============================================================
import logging
from datetime import datetime, timedelta

from database import db

log = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "in_progress", "submitted", "approved"}


def init_compliance_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compliance_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                dept         TEXT,
                category     TEXT,
                title        TEXT NOT NULL,
                description  TEXT,
                due_date     TEXT,
                status       TEXT DEFAULT 'pending',
                assigned_to  TEXT,
                file_path    TEXT,
                created_at   TEXT,
                updated_at   TEXT
            )
        """)


def list_items(dept: str = None, category: str = None, status: str = None) -> list:
    init_compliance_table()
    with db() as conn:
        q = "SELECT * FROM compliance_items WHERE 1=1"
        params = []
        if dept:
            q += " AND UPPER(COALESCE(dept,'')) = ?"
            params.append(dept.upper())
        if category:
            q += " AND UPPER(COALESCE(category,'')) = ?"
            params.append(category.upper())
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY (due_date IS NULL), due_date ASC"
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def create_item(dept, category, title, description, due_date, assigned_to) -> dict:
    init_compliance_table()
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO compliance_items
              (dept, category, title, description, due_date, status, assigned_to, file_path, created_at, updated_at)
            VALUES (?,?,?,?,?, 'pending', ?, '', ?, ?)
        """, (dept, category, title, description, due_date, assigned_to, now, now))
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM compliance_items WHERE id=?", (new_id,)).fetchone()
        return dict(row)


def update_item(item_id: int, status: str = None, **fields) -> dict:
    init_compliance_table()
    with db() as conn:
        existing = conn.execute("SELECT * FROM compliance_items WHERE id=?", (item_id,)).fetchone()
        if not existing:
            return None

        updates = {}
        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(f"Invalid status: {status}")
            updates["status"] = status
        for k in ("dept", "category", "title", "description", "due_date", "assigned_to", "file_path"):
            if k in fields and fields[k] is not None:
                updates[k] = fields[k]

        if updates:
            updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE compliance_items SET {set_clause} WHERE id=?",
                         (*updates.values(), item_id))

        row = conn.execute("SELECT * FROM compliance_items WHERE id=?", (item_id,)).fetchone()
        return dict(row)


def delete_item(item_id: int) -> bool:
    init_compliance_table()
    with db() as conn:
        cur = conn.execute("DELETE FROM compliance_items WHERE id=?", (item_id,))
        return cur.rowcount > 0


def get_upcoming(days: int = 14, dept: str = None) -> list:
    """Items due within the next `days` days that aren't already approved."""
    init_compliance_table()
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    with db() as conn:
        q = """
            SELECT * FROM compliance_items
            WHERE due_date IS NOT NULL AND due_date != ''
              AND due_date >= ? AND due_date <= ?
              AND status != 'approved'
        """
        params = [today, cutoff]
        if dept:
            q += " AND UPPER(COALESCE(dept,'')) = ?"
            params.append(dept.upper())
        q += " ORDER BY due_date ASC"
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]
