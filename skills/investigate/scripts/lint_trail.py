#!/usr/bin/env python3
"""Lint an investigate trail file for structural validity.

Usage: lint_trail.py <trail.md> [<trail.md> ...]

Checks structure only. It cannot check whether evidence was reported raw or
whether Claude answered its own question; only a human reading the transcript
can do that.
"""
import sys
from pathlib import Path


def parse_frontmatter(text):
    """Split leading YAML-style frontmatter into a dict of flat scalars.

    Hand-rolled because skill scripts are standard library only, and trail
    frontmatter is always flat key/value pairs.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text[end + 5:]


def split_sections(body):
    """Map each level-two heading to the raw text beneath it."""
    sections = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def parse_table(text):
    """Return the data rows of a markdown table, without header or separator."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(set(cell) <= set("-: ") and cell for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def parse_evidence(text):
    """Return evidence records keyed by id, plus every id in document order.

    The id list keeps repeats so duplicates can be reported; the dict cannot.
    """
    records = {}
    ids = []
    current = None
    for line in text.splitlines():
        if line.startswith("### "):
            current = line[4:].strip()
            ids.append(current)
            records.setdefault(current, {})
        elif current and line.strip().startswith("- ") and ":" in line:
            key, _, value = line.strip()[2:].partition(":")
            records[current][key.strip()] = value.strip()
    return records, ids


STATES = ("reasoned", "accepted", "refuted", "open")
REPLAYABLE = ("yes", "no", "drifts")
FRAMED_BY = ("human", "claude")

REQUIRED_KEYS = {
    "code": ("citation",),
    "metrics": ("target", "query", "window", "returned"),
    "logs": ("target", "query", "window", "returned"),
    "graph": ("target", "query", "run", "returned"),
    "shell": ("command", "context", "run", "returned"),
    "link": ("url", "points_at"),
    "conversation": ("permalink", "author", "ts"),
}

# `returned` may be empty because its content lives in a following fenced block.
MAY_BE_EMPTY = ("returned",)


def lint(text):
    """Return one message per structural problem. Empty means the trail is valid."""
    problems = []
    meta, body = parse_frontmatter(text)
    sections = split_sections(body)

    for required in ("Findings", "Evidence", "Not checked"):
        if required not in sections:
            problems.append(f"missing required section: ## {required}")

    records, ids = parse_evidence(sections.get("Evidence", ""))
    for evidence_id in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate evidence id: {evidence_id}")

    for evidence_id in sorted(records):
        record = records[evidence_id]
        form = record.get("form", "")
        if form not in REQUIRED_KEYS:
            problems.append(
                f"{evidence_id}: unknown form {form!r}; expected one of "
                + ", ".join(sorted(REQUIRED_KEYS))
            )
        else:
            for key in REQUIRED_KEYS[form]:
                if key not in record:
                    problems.append(f"{evidence_id}: form {form} is missing {key}")
                elif not record[key] and key not in MAY_BE_EMPTY:
                    problems.append(f"{evidence_id}: {key} is empty")
        replayable = record.get("replayable", "")
        if replayable not in REPLAYABLE:
            problems.append(
                f"{evidence_id}: replayable is {replayable!r}; expected one of "
                + ", ".join(REPLAYABLE)
            )

    for row in parse_table(sections.get("Findings", "")):
        if len(row) != 5:
            problems.append(f"finding row needs 5 columns, found {len(row)}: {row}")
            continue
        finding_id, _, state, cited, framed_by = row
        if state not in STATES:
            problems.append(
                f"{finding_id}: state is {state!r}; expected one of "
                + ", ".join(STATES)
            )
        if framed_by not in FRAMED_BY:
            problems.append(
                f"{finding_id}: framed by is {framed_by!r}; expected human or claude"
            )
        cited_ids = [part.strip() for part in cited.split(",") if part.strip()]
        if state != "open" and not cited_ids:
            problems.append(f"{finding_id}: state {state} cites no evidence")
        for cited_id in cited_ids:
            if cited_id not in records:
                problems.append(f"{finding_id}: cites undefined evidence id {cited_id}")

    if meta.get("status") == "closed" and not sections.get("Synthesis", "").strip():
        problems.append("status is closed but the synthesis is empty")

    return problems


def main(argv):
    """Lint every path given. Return 0 when all are clean, 1 otherwise."""
    failed = False
    for arg in argv:
        path = Path(arg)
        problems = lint(path.read_text())
        for problem in problems:
            print(f"{path}: {problem}")
            failed = True
        if not problems:
            print(f"{path}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
