# =============================================================
# ai_summary.py — NEW FILE (additive, does not touch existing code)
#
# Turns raw attendance statistics into a short, HOD-facing
# natural-language paragraph.
#
#   generate_report_summary(stats)  -> rule-based, offline, free,
#                                        always works.
#   generate_ai_summary(stats)      -> calls Anthropic Claude if
#                                        ANTHROPIC_API_KEY is set in
#                                        .env, else silently falls
#                                        back to generate_report_summary().
# =============================================================
import os
import logging

log = logging.getLogger(__name__)


# ── Rule-based summary (no external dependency, no cost) ───────
def generate_report_summary(stats: dict) -> str:
    """
    stats expected keys (all optional, missing ones are skipped):
      total_students, avg_attendance, critical_count, warning_count,
      below_75_count, dept, lowest_section: {section, avg_pct},
      lowest_year: {year, avg_pct}, trend_direction: 'up'|'down'|'flat'
    Returns a 3-5 sentence paragraph.
    """
    dept   = stats.get("dept") or "the department"
    total  = stats.get("total_students", 0)
    avg    = stats.get("avg_attendance", 0)
    crit   = stats.get("critical_count", 0)
    warn   = stats.get("warning_count", 0)
    below  = stats.get("below_75_count", 0)
    trend  = stats.get("trend_direction", "flat")
    lsec   = stats.get("lowest_section") or {}
    lyr    = stats.get("lowest_year") or {}

    sentences = []

    # Opening line — overall health
    if avg >= 85:
        sentences.append(
            f"{dept} is in excellent shape with {total} active students "
            f"averaging {avg}% attendance.")
    elif avg >= 75:
        sentences.append(
            f"{dept} attendance is healthy overall — {total} students "
            f"averaging {avg}%, just above the required 75% threshold.")
    else:
        sentences.append(
            f"{dept} attendance needs attention — {total} students "
            f"averaging only {avg}%, below the required 75% threshold.")

    # Trend
    if trend == "down":
        sentences.append("Attendance has been trending downward recently and should be monitored closely.")
    elif trend == "up":
        sentences.append("Attendance has been improving over the recent period.")

    # Critical / warning counts
    if crit:
        sentences.append(
            f"{crit} student{'s are' if crit != 1 else ' is'} in the critical "
            f"zone (below 60%) and need{'s' if crit == 1 else ''} immediate parent contact.")
    if warn:
        sentences.append(
            f"{warn} more student{'s are' if warn != 1 else ' is'} in the warning "
            f"zone (60–75%) and should be followed up this week.")

    # Worst section / year callouts
    if lsec.get("section") and lsec.get("avg_pct", 100) < avg:
        sentences.append(
            f"Section {lsec['section']} is the weakest at {lsec['avg_pct']}%, "
            f"below the department average.")
    if lyr.get("year") and lyr.get("avg_pct", 100) < 75:
        sentences.append(
            f"{lyr['year']} Year has the lowest attendance at {lyr['avg_pct']}%.")

    if not below and not crit and not warn:
        sentences.append("No students currently require escalation.")

    return " ".join(sentences)


# ── Optional Claude-powered version (graceful fallback) ────────
def generate_ai_summary(stats: dict) -> str:
    """
    Tries to call the Anthropic API for a sharper, more natural summary.
    Falls back to generate_report_summary() on ANY failure — missing key,
    network error, rate limit, etc. Never raises.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return generate_report_summary(stats)

    try:
        import json
        import urllib.request

        prompt = (
            "You are summarizing attendance data for a college HOD dashboard. "
            "Write a tight 3-4 sentence summary, plain English, no markdown, "
            "no bullet points, professional tone. Focus on what needs action. "
            f"Data: {json.dumps(stats)}"
        )

        body = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        text = " ".join(p.strip() for p in parts if p.strip())
        return text or generate_report_summary(stats)

    except Exception as exc:
        log.warning("AI summary call failed, using rule-based fallback: %s", exc)
        return generate_report_summary(stats)
