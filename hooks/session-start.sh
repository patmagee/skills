#!/usr/bin/env bash
# experience-memory: inject the topic index at session start.
# Silent no-op when the store or index does not exist yet.
set -u
STORE="${EXPERIENCE_STORE:-$HOME/.experience-memory}"
INDEX="$STORE/index.md"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="$SCRIPT_DIR/../skills/experience-memory/scripts/experience.py"

if [ -f "$INDEX" ] && [ -s "$INDEX" ]; then
  echo "<experience-memory-index>"
  echo "Recurring-work knowledge topics with distilled bundles. Before starting"
  echo "work that matches a topic below, pull its bundle first:"
  echo "  python3 $CLI bundle <topic-slug>"
  echo "If work is substantive but matches no topic, pull the global bundle:"
  echo "  python3 $CLI bundle --global"
  echo ""
  cat "$INDEX"
  echo "</experience-memory-index>"
fi
exit 0
