#!/usr/bin/env python3
"""experience-memory store CLI.

All mutations of the experience store go through this script; the model
never edits store files by hand. The store holds topic-keyed forum
threads of evidence-grounded claims, typed attempt records, and
distilled bundles. See the skill's SKILL.md for the capture, pull, and
distill flows.
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_STORE = str(Path.home() / ".experience-memory")
DISTILL_THRESHOLD = 5
BUNDLE_SECTIONS = [
    "## Transferable insights",
    "## Confirmed constraints",
    "## Rejected hypotheses",
    "## Pitfalls",
    "## Checks",
    "## Next steps",
]
BUNDLE_SIZE_WARN_LINES = 150
LOCK_STALE_SECONDS = 600

OUTCOMES = {"solved", "partial", "failed", "abandoned"}
STANCES = {"NEW", "AGREE", "DISAGREE", "SYNTHESIZE"}
CONFIDENCES = {"high", "medium", "low"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class StoreError(Exception):
    """A user-fixable store or payload problem; printed and exit code 2."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def read_jsonl(path):
    """Read a JSONL file, skipping corrupt lines with a stderr warning."""
    records = []
    if not path.is_file():
        return records
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"warning: skipping corrupt line {lineno} in {path}",
                      file=sys.stderr)
    return records


def append_jsonl(path, record):
    """Append one record as a single O_APPEND write (atomic at this size)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def write_atomic(path, text):
    """Write via temp file + rename so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json_atomic(path, obj):
    write_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def topics_root(store):
    return store / "topics"


def topic_dir(store, slug):
    return topics_root(store) / slug


def iter_topic_metas(store):
    """Yield topic meta dicts sorted by slug, skipping unreadable ones."""
    root = topics_root(store)
    if not root.is_dir():
        return
    for tdir in sorted(root.iterdir()):
        meta_path = tdir / "topic.json"
        if not meta_path.is_file():
            continue
        try:
            yield json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(f"warning: skipping unreadable {meta_path}", file=sys.stderr)


def load_topic(store, slug):
    meta_path = topic_dir(store, slug) / "topic.json"
    if not meta_path.is_file():
        valid = [m["slug"] for m in iter_topic_metas(store)]
        raise StoreError(
            f"unknown topic '{slug}'; valid topics: {', '.join(valid) or '(none)'}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def topic_posts(store, slug):
    return read_jsonl(topic_dir(store, slug) / "posts.jsonl")


def topic_attempts(store, slug):
    return read_jsonl(topic_dir(store, slug) / "attempts.jsonl")


def next_id(records):
    return max((r.get("id", 0) for r in records), default=0) + 1


def undistilled_posts(meta, posts):
    watermark = meta.get("distilled_through_post_id", 0)
    return [p for p in posts if p.get("id", 0) > watermark]


def parse_payload(payload_json):
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as e:
        raise StoreError(f"payload is not valid JSON: {e}")
    if not isinstance(payload, dict):
        raise StoreError("payload must be a JSON object")
    return payload


def require_fields(payload, fields):
    missing = [f for f in fields if not str(payload.get(f, "")).strip()]
    if missing:
        raise StoreError(f"missing or empty fields: {', '.join(missing)}")


def validate_attempt(payload):
    require_fields(payload, ["task", "outcome", "verification"])
    if payload["outcome"] not in OUTCOMES:
        raise StoreError(f"outcome must be one of {sorted(OUTCOMES)}")
    if "bundle_used" in payload and not isinstance(payload["bundle_used"], bool):
        raise StoreError("bundle_used must be a boolean")


def cmd_attempt(store, slug, payload_json):
    load_topic(store, slug)
    payload = parse_payload(payload_json)
    validate_attempt(payload)
    attempts = topic_attempts(store, slug)
    record = dict(payload)
    record["id"] = next_id(attempts)
    record["ts"] = utc_now()
    append_jsonl(topic_dir(store, slug) / "attempts.jsonl", record)
    print(f"recorded attempt {record['id']} in {slug}")


def regenerate_index(store):
    """Rebuild index.md: one line per topic, injected at SessionStart."""
    lines = []
    for meta in iter_topic_metas(store):
        slug = meta["slug"]
        posts = topic_posts(store, slug)
        und = undistilled_posts(meta, posts)
        if not (topic_dir(store, slug) / "bundle.md").is_file():
            status = "no bundle yet"
        elif und:
            status = f"{len(und)} undistilled"
        else:
            status = "bundle fresh"
        marker = " ⚡ distill ready" if len(und) >= DISTILL_THRESHOLD else ""
        hook = meta.get("hook", meta.get("title", slug))
        lines.append(f"- {slug} — {hook} [{len(posts)} posts, {status}{marker}]")
    if (store / "global" / "bundle.md").is_file():
        lines.append("- global — cross-topic principles (pull when work matches no topic)")
    write_atomic(store / "index.md", "\n".join(lines) + ("\n" if lines else ""))


def cmd_create(store, slug, title, hook, tags):
    if not SLUG_RE.match(slug):
        raise StoreError(
            "slug must be lowercase letters, digits, and hyphens (e.g. flaky-ci-repo-x)")
    tdir = topic_dir(store, slug)
    if (tdir / "topic.json").exists():
        raise StoreError(f"topic '{slug}' already exists")
    tdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "slug": slug,
        "title": title,
        "hook": hook,
        "tags": tags,
        "created": utc_now(),
        "distilled_through_post_id": 0,
    }
    write_json_atomic(tdir / "topic.json", meta)
    regenerate_index(store)
    print(f"created topic '{slug}'")


def cmd_topics(store):
    found = False
    for meta in iter_topic_metas(store):
        found = True
        slug = meta["slug"]
        posts = topic_posts(store, slug)
        und = undistilled_posts(meta, posts)
        ready = " | DISTILL READY" if len(und) >= DISTILL_THRESHOLD else ""
        tags = ",".join(meta.get("tags", []))
        print(f"{slug}: {meta['title']} | tags={tags} | "
              f"{len(posts)} posts, {len(und)} undistilled{ready}")
    if not found:
        print("no topics yet")


def build_parser():
    p = argparse.ArgumentParser(prog="experience.py", description=__doc__)
    p.add_argument("--store", default=DEFAULT_STORE,
                   help="store directory (default: ~/.experience-memory)")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("create", help="create a new topic")
    sp.add_argument("topic")
    sp.add_argument("--title", required=True)
    sp.add_argument("--hook", required=True,
                    help="one concrete line for the injected index")
    sp.add_argument("--tags", default="", help="comma-separated tags (repo, domain)")

    sp = sub.add_parser("attempt", help="append an attempt record")
    sp.add_argument("topic")
    sp.add_argument("--json", required=True, dest="payload",
                    help="attempt record as a JSON object")

    sub.add_parser("topics", help="list topics with counts")
    sub.add_parser("index", help="regenerate index.md")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    store = Path(args.store).expanduser()
    try:
        if args.command == "create":
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            cmd_create(store, args.topic, args.title, args.hook, tags)
        elif args.command == "attempt":
            cmd_attempt(store, args.topic, args.payload)
        elif args.command == "topics":
            cmd_topics(store)
        elif args.command == "index":
            regenerate_index(store)
            print("index regenerated")
        return 0
    except StoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
