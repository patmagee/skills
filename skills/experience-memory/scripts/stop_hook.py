#!/usr/bin/env python3
"""Stop-hook logic for experience-memory capture reminders.

Reads the hook event JSON on stdin. When the session looks substantive
and no reminder has fired yet for this session, prints a block decision
so the model sees the reminder once. Always exits 0; a broken store or
transcript must never block a session.
"""
import json
import os
import sys
import time
from pathlib import Path

TOOL_USE_THRESHOLD = 15
MARKER_MAX_AGE_SECONDS = 7 * 24 * 3600
# Both spacings occur depending on the JSON serializer that wrote the line.
TOOL_USE_NEEDLES = ('"type":"tool_use"', '"type": "tool_use"')

REMINDER = (
    "experience-memory: this session was substantive. If hypotheses were "
    "tested or something non-obvious was learned, offer to run the "
    "experience-memory capture flow (topic match, attempt record, claims "
    "with stances). If nothing here is worth keeping, simply finish your "
    "response; this reminder fires at most once per session."
)


def count_tool_uses(transcript_path):
    count = 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                count += sum(line.count(n) for n in TOOL_USE_NEEDLES)
    except OSError:
        return 0
    return count


def should_fire(event, store_dir, marker_dir):
    """Decide whether to emit the reminder; writes the marker when firing."""
    if event.get("stop_hook_active"):
        return False
    if not store_dir.is_dir():
        return False
    session_id = event.get("session_id")
    transcript = event.get("transcript_path")
    if not session_id or not transcript:
        return False
    marker = marker_dir / str(session_id)
    if marker.exists():
        return False
    if count_tool_uses(transcript) <= TOOL_USE_THRESHOLD:
        return False
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(int(time.time())))
    return True


def cleanup_markers(marker_dir):
    now = time.time()
    try:
        for m in marker_dir.iterdir():
            if now - m.stat().st_mtime > MARKER_MAX_AGE_SECONDS:
                m.unlink(missing_ok=True)
    except OSError:
        pass


def main():
    try:
        event = json.load(sys.stdin)
        store = Path(os.environ.get(
            "EXPERIENCE_STORE", str(Path.home() / ".experience-memory")))
        marker_dir = store / "markers"
        if should_fire(event, store, marker_dir):
            cleanup_markers(marker_dir)
            print(json.dumps({"decision": "block", "reason": REMINDER}))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
