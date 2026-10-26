# =============================================================
# database_postgres.py — Unified Database Consolidation Facade
#
# NOTE: In accordance with enterprise architectural consolidation,
#       database_postgres.py and database.py are unified into a single
#       centralized DatabaseManager (app/database/manager.py).
#       This file remains as an idempotent shim so any legacy references
#       seamlessly route to the unified database manager.
# =============================================================
import logging
import database as _real_db
from app.database.manager import DatabaseManager, get_connection, session

log = logging.getLogger(__name__)

# Forward all core symbols from unified manager and database.py
manager = DatabaseManager.get_instance()
DB_PATH = _real_db.DB_PATH
db = _real_db.db
get_db_connection = _real_db.get_db_connection
init_db = _real_db.init_db
init_all_tables = _real_db.init_all_tables

# Forward all other attributes dynamically
for _attr in dir(_real_db):
    if not _attr.startswith("__") and _attr not in globals():
        globals()[_attr] = getattr(_real_db, _attr)

log.debug("Unified Database Manager active (database_postgres.py facade -> database.py)")
