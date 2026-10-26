import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import db

with db._connect() as conn:
    ev_types = conn.execute("SELECT event_type, count(*) FROM rescue_status_events GROUP BY event_type").fetchall()
    print("Rescue status event types:", dict(ev_types))

    recent_events = conn.execute("SELECT * FROM rescue_status_events ORDER BY id DESC LIMIT 5").fetchall()
    print("\nRecent 5 rescue events:")
    for ev in recent_events:
        print(dict(ev))

    teams = conn.execute("SELECT * FROM admin_teams").fetchall()
    print("\nAdmin teams:")
    for t in teams:
        print(dict(t))
