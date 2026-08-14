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
