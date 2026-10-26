"""
app/repositories/base.py
Enterprise Base Repository providing centralized DB access, transaction safety,
and optimized connection execution.
"""

import sqlite3
from typing import Any, Dict, List, Optional
from app.database.manager import DatabaseManager


class BaseRepository:
    """Base repository handling SQLite connection lifecycle and query execution."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager.get_instance()

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executes a query and returns all rows as dictionaries."""
        with self.db_manager.session(write=False) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Executes a query and returns a single row as a dictionary or None."""
        with self.db_manager.session(write=False) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Executes an INSERT/UPDATE/DELETE query with transactional write safety."""
        with self.db_manager.session(write=True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid or cursor.rowcount
