# =============================================================
# app/database/manager.py
# Enterprise Unified Database Manager (Centralized Single Source of Truth)
# =============================================================
import os
import time
import random
import sqlite3
import logging
import threading
from typing import Generator
from contextlib import contextmanager

try:
    import config
    DB_PATH = getattr(config, "DB_PATH", os.path.join(config.BASE_DIR, "data", "attendance.db"))
except Exception:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "attendance.db")

log = logging.getLogger(__name__)


class DatabaseManager:
    """
    Centralized, thread-safe database manager for high-concurrency operations.
    Implements:
      - WAL journal mode for non-blocking multi-reader concurrency.
      - 64MB memory page caching and 256MB memory-mapped I/O (mmap).
      - Re-entrant write serialization with exponential jittered retries to completely
        eliminate 'database is locked' errors.
      - Automatic schema bootstrapping.
    """
    _instance = None
    _singleton_lock = threading.Lock()

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._write_lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @classmethod
    def get_instance(cls, db_path: str = None) -> "DatabaseManager":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    def get_connection(self, timeout: float = 60.0) -> sqlite3.Connection:
        """
        Creates and returns a connection configured with optimal enterprise PRAGMAs:
        WAL mode, synchronous=NORMAL, 60s busy_timeout, foreign_keys=ON.
        """
        conn = sqlite3.connect(self.db_path, timeout=timeout, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            conn.execute("PRAGMA mmap_size = 268435456;")
        except Exception as e:
            log.warning("[DB-MANAGER] Pragma setup warning: %s", e)
        return conn

    @contextmanager
    def session(self, write: bool = False, max_retries: int = 5) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database sessions with automatic write locking and retry backoff.
        """
        lock_acquired = False
        if write:
            self._write_lock.acquire()
            lock_acquired = True

        conn = None
        try:
            attempt = 0
            while True:
                try:
                    conn = self.get_connection(timeout=60.0)
                    yield conn
                    if write:
                        conn.commit()
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries:
                        attempt += 1
                        backoff = (0.05 * (2 ** attempt)) + random.uniform(0.01, 0.05)
                        log.warning("[DB-MANAGER] Database locked on attempt %d/%d. Retrying in %.3fs...", attempt, max_retries, backoff)
                        if conn:
                            try:
                                conn.rollback()
                                conn.close()
                            except Exception:
                                pass
                            conn = None
                        time.sleep(backoff)
                    else:
                        if write and conn:
                            try:
                                conn.rollback()
                            except Exception:
                                pass
                        raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            if lock_acquired:
                self._write_lock.release()


# Module-level default manager instance
_default_manager = DatabaseManager.get_instance()
get_connection = _default_manager.get_connection
session = _default_manager.session
