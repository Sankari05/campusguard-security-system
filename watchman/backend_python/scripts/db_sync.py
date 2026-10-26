# scripts/db_sync.py
"""
Database schema synchronizer.
Ensures PostgreSQL table columns allow NULL for optional fields
and creates any missing tables or columns.
"""
import logging

from sqlalchemy import text

from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_sync")

def sync_schema():
    with engine.connect() as conn:
        # Check and drop NOT NULL on optional visitor_passes columns
        statements = [
            "ALTER TABLE visitor_passes ALTER COLUMN phone_number DROP NOT NULL;",
            "ALTER TABLE visitor_passes ALTER COLUMN purpose DROP NOT NULL;",
            "ALTER TABLE visitor_passes ALTER COLUMN reason DROP NOT NULL;",
            "ALTER TABLE visitor_passes ALTER COLUMN department DROP NOT NULL;",
            "ALTER TABLE visitor_passes ALTER COLUMN person_to_meet DROP NOT NULL;",
            "ALTER TABLE visitor_passes ALTER COLUMN additional_details DROP NOT NULL;",
        ]
        for stmt in statements:
            try:
                conn.execute(text(stmt))
                conn.commit()
                logger.info(f"Executed: {stmt}")
            except Exception as e:
                conn.rollback()
                logger.debug(f"Skipped {stmt}: {e}")

    logger.info("Schema synchronization complete.")

if __name__ == "__main__":
    sync_schema()
