import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

"""
migrate_od_two_stage.py
------------------------
ONE-OFF backward-compat data migration for the Step 1 two-stage
(Faculty -> HOD) OD approval pipeline.

BACKGROUND
  Before Step 1, od_requests was single-stage: a decision (Approved/
  Rejected) was written straight into status/decided_by/decided_at/
  remarks. Step 1 added faculty_status/faculty_decided_by/... and
  hod_status/hod_decided_by/... so the pipeline could track Faculty's
  and HOD's decisions separately. The new columns are populated going
  forward by faculty_decide_od_request()/hod_decide_od_request(), but
  any row that was already Approved/Rejected *before* Step 1 shipped
  has those new columns sitting empty.

  The Step 7 student tracker (and the Step 9 patch alongside it) reads
  faculty_status/hod_decided_by to render the 4-stage stepper and to
  tell "Rejected by Faculty" apart from "Rejected by HOD". An old row
  with status='Approved'/'Rejected' but faculty_status='' doesn't fail,
  but it IS misread: the tracker has no record of who actually decided
  it, so the Faculty Review step renders as "Awaiting faculty review"
  even though the request was finalized years ago.

WHAT THIS SCRIPT DOES
  For every od_requests row where:
      status IN ('Approved', 'Rejected')
      AND (faculty_status IS NULL OR faculty_status = '')
      AND decided_by IS NOT NULL AND decided_by != ''
  it backfills the OLD single decision into the FACULTY side of the
  pipeline (never the HOD side — under the old schema there was only
  one decision-maker, and that maps to "Faculty" the same way Step 2
  treats leave's sole decision-maker as Faculty):
      faculty_status     = status
      faculty_decided_by  = decided_by
      faculty_decided_at  = decided_at
      faculty_remarks     = remarks
  hod_status/hod_decided_by/... are intentionally left untouched
  (blank) — that blank is exactly the signal the tracker uses to know
  HOD never reviewed these legacy rows (see student_portal_db.py's
  "approved_legacy" / "rejected_by_faculty" handling).

  status/decided_by/decided_at/remarks themselves are NOT modified —
  they already hold the correct historical outcome and are kept as
  the legacy/back-compat mirror columns, same as before.

SAFETY
  - Read-only WHERE guard means this is naturally idempotent: once a
    row's faculty_status is backfilled, it no longer matches the
    WHERE clause, so running this script twice is harmless (the
    second run just migrates 0 rows).
  - This file is NOT imported or called anywhere else (no server
    startup path runs it). It is meant to be invoked manually, once,
    after deploying the Step 1 schema change to an existing database:

        python3 migrate_od_two_stage.py

Run:  python3 migrate_od_two_stage.py
"""
import logging

from database import db
import database_faculty_requests as freq

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("migrate_od_two_stage")


def migrate() -> int:
    """Backfill faculty_* columns for pre-Step-1 OD decisions.
    Returns the number of rows migrated."""
    # Make sure the two-stage columns actually exist before we query
    # them — covers the case where this script is run against a DB
    # that predates Step 1 entirely and has never been touched by the
    # app's own (additive, idempotent) ALTER TABLE migration.
    freq.init_od_table()

    with db() as conn:
        rows = conn.execute(
            """SELECT id, status, decided_by, decided_at, remarks
               FROM od_requests
               WHERE status IN ('Approved', 'Rejected')
                 AND (faculty_status IS NULL OR faculty_status = '')
                 AND decided_by IS NOT NULL AND decided_by != ''"""
        ).fetchall()

        migrated = 0
        for row in rows:
            conn.execute(
                """UPDATE od_requests
                   SET faculty_status=?, faculty_decided_by=?,
                       faculty_decided_at=?, faculty_remarks=?
                   WHERE id=?""",
                (row["status"], row["decided_by"], row["decided_at"] or "",
                 row["remarks"] or "", row["id"]),
            )
            migrated += 1
            log.info(
                "  migrated od_request #%s: status=%s decided_by=%s -> faculty_status=%s faculty_decided_by=%s",
                row["id"], row["status"], row["decided_by"], row["status"], row["decided_by"],
            )

    return migrated


def main():
    log.info("Scanning od_requests for pre-two-stage (old schema) decisions...")
    count = migrate()
    if count:
        log.info("Done. Migrated %d row(s) — faculty_status/faculty_decided_by/"
                  "faculty_decided_at/faculty_remarks backfilled from the old "
                  "status/decided_by/decided_at/remarks columns.", count)
    else:
        log.info("Done. No rows needed migration (none found with status set "
                 "but faculty_status empty).")


if __name__ == "__main__":
    main()
