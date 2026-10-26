-- =============================================================
-- migrate_legacy_to_faculty.sql  —  EduTrack Pro v10.1
-- One-shot migration: verify and maintain unified faculty table.
-- =============================================================

-- Verify faculty table
SELECT 'faculty_rows' AS check_name, COUNT(*) AS result FROM faculty;
