#!/usr/bin/env bash
# experience-memory: one-shot capture reminder on Stop. All logic lives
# in stop_hook.py; this wrapper only resolves the path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/../skills/experience-memory/scripts/stop_hook.py"
