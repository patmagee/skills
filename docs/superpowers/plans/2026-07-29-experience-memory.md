# experience-memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the experience-memory skill: a global, topic-keyed store of evidence-grounded claims with stances, hybrid hook-prompted capture, and threshold-triggered distillation into typed bundles, per the approved spec at `docs/superpowers/specs/2026-07-29-experience-memory-design.md`.

**Architecture:** A stdlib-only Python CLI (`experience.py`) owns all store mutations at `~/.experience-memory/`. Two plugin hooks (SessionStart index injection, Stop capture reminder) are thin shell wrappers over Python. The skill (SKILL.md plus a distiller agent prompt) orchestrates three flows: capture, pull, distill.

**Tech Stack:** Python 3 standard library only, bash for hook wrappers, `unittest` for tests. No third-party dependencies.

## Global Constraints

- Python 3 stdlib only. No pip installs, no venv.
- Default store path is `~/.experience-memory/`; every CLI invocation accepts `--store <path>` and tests MUST use a temp-dir store, never the real one.
- Distill threshold is 5 undistilled posts.
- Bundle files MUST contain exactly these six section headers, in this order: `## Transferable insights`, `## Confirmed constraints`, `## Rejected hypotheses`, `## Pitfalls`, `## Checks`, `## Next steps`.
- `attempts.jsonl` and `posts.jsonl` are append-only; distillation advances a `distilled_through_post_id` watermark in `topic.json` and never mutates post lines.
- Hooks must always exit 0 and emit nothing on internal error; they must never block a session.
- Reading a missing topic is an error that lists valid topics; topics are only created by the explicit `create` command.
- Repo conventions: skill lives at `skills/experience-memory/` with `SKILL.md` at its top level; root `README.md` and root `CLAUDE.md` skill lists must be updated.
- Run tests from the skill directory: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`.
- Commit messages state the why; never `git add .` or `git add -A`; never stage `.claude/work/`.

## File Structure

```
skills/experience-memory/
├── SKILL.md                 # entry point: capture / pull / distill flows (Task 9)
├── README.md                # human docs (Task 10)
├── CLAUDE.md                # dev docs + e2e walkthrough (Task 10)
├── agents/
│   └── distiller.md         # distiller subagent prompt (Task 8)
├── references/
│   └── schemas.md           # payload schemas for the capture flow (Task 8)
├── scripts/
│   ├── experience.py        # store CLI (Tasks 1-5)
│   └── stop_hook.py         # Stop-hook decision logic (Task 6)
└── tests/
    ├── test_experience.py   # CLI tests (Tasks 1-5)
    └── test_stop_hook.py    # hook logic tests (Task 6)
hooks/                       # plugin root (repo root), created in Task 7
├── hooks.json               # plugin hook registration
├── session-start.sh         # injects index.md as context
└── capture-reminder.sh      # execs stop_hook.py
```

---

### Task 1: CLI foundation — store helpers, `create`, `topics`, index regeneration

**Files:**
- Create: `skills/experience-memory/scripts/experience.py`
- Test: `skills/experience-memory/tests/test_experience.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces (later tasks rely on these exact names):
  - `StoreError(Exception)`
  - `utc_now() -> str` (ISO-8601 UTC, seconds precision)
  - `read_jsonl(path: Path) -> list[dict]` (skips corrupt lines, warns to stderr)
  - `append_jsonl(path: Path, record: dict) -> None` (single O_APPEND write)
  - `write_atomic(path: Path, text: str) -> None` (temp file + `os.replace`)
  - `write_json_atomic(path: Path, obj) -> None`
  - `topics_root(store: Path) -> Path`, `topic_dir(store: Path, slug: str) -> Path`
  - `load_topic(store, slug) -> dict` (raises StoreError listing valid topics)
  - `topic_posts(store, slug) -> list[dict]`, `topic_attempts(store, slug) -> list[dict]`
  - `next_id(records: list[dict]) -> int`
  - `undistilled_posts(meta: dict, posts: list[dict]) -> list[dict]`
  - `regenerate_index(store: Path) -> None`
  - `cmd_create(store, slug, title, hook, tags)`, `cmd_topics(store)`
  - `main(argv: list[str] | None = None) -> int` (0 ok, 2 on StoreError)
  - Constants: `DISTILL_THRESHOLD = 5`, `BUNDLE_SECTIONS`, `BUNDLE_SIZE_WARN_LINES = 150`, `LOCK_STALE_SECONDS = 600`, `OUTCOMES`, `STANCES`, `CONFIDENCES`

- [ ] **Step 1: Write the failing tests**

Create `skills/experience-memory/tests/test_experience.py`:

```python
"""Tests for the experience-memory store CLI.

Every test runs against a temp-dir store via --store; the real store at
~/.experience-memory/ is never touched.
"""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("experience", SCRIPTS / "experience.py")
experience = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(experience)


def run_cli(store, *argv):
    """Invoke main() with a temp store; return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = experience.main(["--store", str(store), *argv])
    return code, out.getvalue(), err.getvalue()


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def create_topic(self, slug="topic-a", hook="hook text"):
        code, out, err = run_cli(
            self.store, "create", slug, "--title", f"Title of {slug}",
            "--hook", hook, "--tags", "repo-x,debugging")
        assert code == 0, err
        return slug


class TestCreateAndTopics(StoreTestCase):
    def test_create_writes_topic_json_and_index(self):
        self.create_topic("kg-local-dev-setup", hook="gcom proxy gotchas")
        meta = json.loads(
            (self.store / "topics" / "kg-local-dev-setup" / "topic.json").read_text())
        self.assertEqual(meta["slug"], "kg-local-dev-setup")
        self.assertEqual(meta["distilled_through_post_id"], 0)
        self.assertEqual(meta["tags"], ["repo-x", "debugging"])
        index = (self.store / "index.md").read_text()
        self.assertIn("kg-local-dev-setup", index)
        self.assertIn("gcom proxy gotchas", index)
        self.assertIn("no bundle yet", index)

    def test_create_rejects_bad_slug(self):
        code, _, err = run_cli(self.store, "create", "Bad Slug!",
                               "--title", "t", "--hook", "h")
        self.assertEqual(code, 2)
        self.assertIn("slug", err)

    def test_create_rejects_duplicate(self):
        self.create_topic("dup")
        code, _, err = run_cli(self.store, "create", "dup",
                               "--title", "t", "--hook", "h")
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)

    def test_topics_lists_created_topics(self):
        self.create_topic("topic-a")
        self.create_topic("topic-b")
        code, out, _ = run_cli(self.store, "topics")
        self.assertEqual(code, 0)
        self.assertIn("topic-a", out)
        self.assertIn("topic-b", out)
        self.assertIn("0 posts", out)

    def test_topics_empty_store(self):
        code, out, _ = run_cli(self.store, "topics")
        self.assertEqual(code, 0)
        self.assertIn("no topics yet", out)


class TestHelpers(StoreTestCase):
    def test_read_jsonl_skips_corrupt_lines(self):
        p = self.store / "x.jsonl"
        p.write_text('{"id": 1}\nNOT JSON\n{"id": 2}\n')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            records = experience.read_jsonl(p)
        self.assertEqual([r["id"] for r in records], [1, 2])
        self.assertIn("corrupt", err.getvalue())

    def test_next_id(self):
        self.assertEqual(experience.next_id([]), 1)
        self.assertEqual(experience.next_id([{"id": 3}, {"id": 7}]), 8)

    def test_load_topic_missing_lists_valid(self):
        self.create_topic("real-topic")
        with self.assertRaises(experience.StoreError) as ctx:
            experience.load_topic(self.store, "nope")
        self.assertIn("real-topic", str(ctx.exception))

    def test_write_atomic_replaces(self):
        p = self.store / "sub" / "f.md"
        experience.write_atomic(p, "one")
        experience.write_atomic(p, "two")
        self.assertEqual(p.read_text(), "two")
        leftovers = [x for x in p.parent.iterdir() if x.name.startswith(".tmp-")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: FAIL at import time (`FileNotFoundError` for `scripts/experience.py`).

- [ ] **Step 3: Write the implementation**

Create `skills/experience-memory/scripts/experience.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: PASS (all tests in TestCreateAndTopics and TestHelpers).

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/scripts/experience.py skills/experience-memory/tests/test_experience.py
git commit -m "Add experience-memory CLI foundation: topic create/list and index generation

The CLI is the single integrity boundary for the store; the index is
the small artifact injected at SessionStart."
```

---

### Task 2: `attempt` command

**Files:**
- Modify: `skills/experience-memory/scripts/experience.py`
- Test: `skills/experience-memory/tests/test_experience.py`

**Interfaces:**
- Consumes: `load_topic`, `topic_attempts`, `next_id`, `append_jsonl`, `utc_now`, `StoreError`, `OUTCOMES` from Task 1.
- Produces: `validate_attempt(payload: dict) -> None`, `parse_payload(payload_json: str) -> dict`, `cmd_attempt(store, slug, payload_json)`. Attempt records gain server-side fields `id` (int) and `ts` (str). Task 3's post validation checks `attempt_id` against these ids.

- [ ] **Step 1: Write the failing tests**

Add to `skills/experience-memory/tests/test_experience.py`:

```python
VALID_ATTEMPT = {
    "repo": "asserts-adi", "branch": "fix/onboarding",
    "task": "Cold-onboard dev stack 1729", "outcome": "partial",
    "verification": "graph built but relationship rules empty",
    "bundle_used": True,
}


class TestAttempt(StoreTestCase):
    def test_attempt_appends_record_with_id_and_ts(self):
        self.create_topic("topic-a")
        code, out, err = run_cli(self.store, "attempt", "topic-a",
                                 "--json", json.dumps(VALID_ATTEMPT))
        self.assertEqual(code, 0, err)
        self.assertIn("recorded attempt 1", out)
        records = experience.read_jsonl(
            self.store / "topics" / "topic-a" / "attempts.jsonl")
        self.assertEqual(records[0]["id"], 1)
        self.assertEqual(records[0]["outcome"], "partial")
        self.assertTrue(records[0]["ts"])

    def test_attempt_rejects_bad_outcome(self):
        self.create_topic("topic-a")
        bad = dict(VALID_ATTEMPT, outcome="great")
        code, _, err = run_cli(self.store, "attempt", "topic-a",
                               "--json", json.dumps(bad))
        self.assertEqual(code, 2)
        self.assertIn("outcome", err)

    def test_attempt_rejects_missing_verification(self):
        self.create_topic("topic-a")
        bad = dict(VALID_ATTEMPT, verification="  ")
        code, _, err = run_cli(self.store, "attempt", "topic-a",
                               "--json", json.dumps(bad))
        self.assertEqual(code, 2)
        self.assertIn("verification", err)

    def test_attempt_rejects_non_bool_bundle_used(self):
        self.create_topic("topic-a")
        bad = dict(VALID_ATTEMPT, bundle_used="yes")
        code, _, err = run_cli(self.store, "attempt", "topic-a",
                               "--json", json.dumps(bad))
        self.assertEqual(code, 2)
        self.assertIn("bundle_used", err)

    def test_attempt_unknown_topic_errors(self):
        code, _, err = run_cli(self.store, "attempt", "nope",
                               "--json", json.dumps(VALID_ATTEMPT))
        self.assertEqual(code, 2)
        self.assertIn("unknown topic", err)

    def test_attempt_invalid_json_payload(self):
        self.create_topic("topic-a")
        code, _, err = run_cli(self.store, "attempt", "topic-a", "--json", "{nope")
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/experience-memory && python3 -m unittest tests.test_experience.TestAttempt -v`
Expected: FAIL (argparse: invalid choice 'attempt').

- [ ] **Step 3: Write the implementation**

Add to `experience.py` after `undistilled_posts`:

```python
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
```

Add the subparser in `build_parser()` before the `index` line:

```python
    sp = sub.add_parser("attempt", help="append an attempt record")
    sp.add_argument("topic")
    sp.add_argument("--json", required=True, dest="payload",
                    help="attempt record as a JSON object")
```

Add the dispatch branch in `main()`:

```python
        elif args.command == "attempt":
            cmd_attempt(store, args.topic, args.payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/scripts/experience.py skills/experience-memory/tests/test_experience.py
git commit -m "Add attempt records to experience-memory

Attempts are the typed outcome table; verification is required so
outcomes stay grounded in checks rather than impressions."
```

---

### Task 3: `post` command with stance validation and threshold notice

**Files:**
- Modify: `skills/experience-memory/scripts/experience.py`
- Test: `skills/experience-memory/tests/test_experience.py`

**Interfaces:**
- Consumes: Task 1 helpers, `parse_payload`/`require_fields` from Task 2.
- Produces: `validate_post(payload, existing_post_ids: set[int], existing_attempt_ids: set[int]) -> None`, `cmd_post(store, slug, payload_json)`. Posts gain server-side `id` and `ts`; `stance_post_id` defaults to `None`. Task 5's distill reads post ids to advance the watermark.

- [ ] **Step 1: Write the failing tests**

Add to `test_experience.py`:

```python
def valid_post(attempt_id=1, stance="NEW", stance_post_id=None):
    return {
        "attempt_id": attempt_id,
        "claim": "Cold onboarding requires the gcom proxy env var",
        "load_bearing_assumption": "model-builder reads GCOM_PROXY_URL at startup",
        "evidence": "startup log: 'gcom client disabled' when var unset",
        "stance": stance,
        "stance_post_id": stance_post_id,
        "proposed_change": "Set GCOM_PROXY_URL before first run",
        "predicted_outcome": "Fresh onboard with var set completes relationship rules",
        "confidence": "medium",
    }


class TestPost(StoreTestCase):
    def seed(self, slug="topic-a"):
        self.create_topic(slug)
        run_cli(self.store, "attempt", slug, "--json", json.dumps(VALID_ATTEMPT))
        return slug

    def test_post_new_appends_and_reports_counts(self):
        slug = self.seed()
        code, out, err = run_cli(self.store, "post", slug,
                                 "--json", json.dumps(valid_post()))
        self.assertEqual(code, 0, err)
        self.assertIn("recorded post 1", out)
        self.assertIn("1 undistilled", out)
        self.assertNotIn("distill ready", out)

    def test_post_new_must_not_set_stance_post_id(self):
        slug = self.seed()
        code, _, err = run_cli(self.store, "post", slug, "--json",
                               json.dumps(valid_post(stance="NEW", stance_post_id=1)))
        self.assertEqual(code, 2)
        self.assertIn("NEW", err)

    def test_post_disagree_requires_existing_stance_post_id(self):
        slug = self.seed()
        code, _, err = run_cli(self.store, "post", slug, "--json",
                               json.dumps(valid_post(stance="DISAGREE", stance_post_id=9)))
        self.assertEqual(code, 2)
        self.assertIn("stance_post_id", err)

    def test_post_disagree_with_valid_reference(self):
        slug = self.seed()
        run_cli(self.store, "post", slug, "--json", json.dumps(valid_post()))
        code, out, err = run_cli(self.store, "post", slug, "--json",
                                 json.dumps(valid_post(stance="DISAGREE", stance_post_id=1)))
        self.assertEqual(code, 0, err)
        self.assertIn("recorded post 2", out)

    def test_post_requires_existing_attempt(self):
        slug = self.seed()
        code, _, err = run_cli(self.store, "post", slug, "--json",
                               json.dumps(valid_post(attempt_id=99)))
        self.assertEqual(code, 2)
        self.assertIn("attempt_id", err)

    def test_post_rejects_bad_confidence(self):
        slug = self.seed()
        bad = dict(valid_post(), confidence="certain")
        code, _, err = run_cli(self.store, "post", slug, "--json", json.dumps(bad))
        self.assertEqual(code, 2)
        self.assertIn("confidence", err)

    def test_threshold_notice_at_five_undistilled(self):
        slug = self.seed()
        for _ in range(4):
            run_cli(self.store, "post", slug, "--json", json.dumps(valid_post()))
        code, out, _ = run_cli(self.store, "post", slug,
                               "--json", json.dumps(valid_post()))
        self.assertEqual(code, 0)
        self.assertIn("distill ready", out)
        index = (self.store / "index.md").read_text()
        self.assertIn("distill ready", index)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/experience-memory && python3 -m unittest tests.test_experience.TestPost -v`
Expected: FAIL (argparse: invalid choice 'post').

- [ ] **Step 3: Write the implementation**

Add to `experience.py` after `validate_attempt`:

```python
POST_REQUIRED_FIELDS = [
    "attempt_id", "claim", "load_bearing_assumption", "evidence",
    "stance", "proposed_change", "predicted_outcome", "confidence",
]


def validate_post(payload, existing_post_ids, existing_attempt_ids):
    require_fields(payload, POST_REQUIRED_FIELDS)
    if payload["stance"] not in STANCES:
        raise StoreError(f"stance must be one of {sorted(STANCES)}")
    if payload["confidence"] not in CONFIDENCES:
        raise StoreError(f"confidence must be one of {sorted(CONFIDENCES)}")
    if payload["attempt_id"] not in existing_attempt_ids:
        raise StoreError(
            f"attempt_id {payload['attempt_id']} not found; record the attempt first")
    if payload["stance"] == "NEW":
        if payload.get("stance_post_id") is not None:
            raise StoreError("stance NEW must not set stance_post_id")
    else:
        ref = payload.get("stance_post_id")
        if ref not in existing_post_ids:
            ids = sorted(existing_post_ids)
            span = (f"thread has posts {ids[0]}-{ids[-1]}"
                    if ids else "thread has no posts yet")
            raise StoreError(
                f"stance {payload['stance']} requires a valid stance_post_id; {span}")


def cmd_post(store, slug, payload_json):
    meta = load_topic(store, slug)
    payload = parse_payload(payload_json)
    posts = topic_posts(store, slug)
    attempts = topic_attempts(store, slug)
    validate_post(payload,
                  {p.get("id") for p in posts},
                  {a.get("id") for a in attempts})
    record = dict(payload)
    record["id"] = next_id(posts)
    record["ts"] = utc_now()
    record.setdefault("stance_post_id", None)
    append_jsonl(topic_dir(store, slug) / "posts.jsonl", record)
    regenerate_index(store)
    posts.append(record)
    und = undistilled_posts(meta, posts)
    print(f"recorded post {record['id']} in {slug} "
          f"({len(posts)} posts, {len(und)} undistilled)")
    if len(und) >= DISTILL_THRESHOLD:
        print(f"distill ready: topic '{slug}' has {len(und)} undistilled posts; "
              "offer to run the distill flow")
```

Add the subparser in `build_parser()`:

```python
    sp = sub.add_parser("post", help="append a claim post to a topic thread")
    sp.add_argument("topic")
    sp.add_argument("--json", required=True, dest="payload",
                    help="post as a JSON object (see references/schemas.md)")
```

Add the dispatch branch in `main()`:

```python
        elif args.command == "post":
            cmd_post(store, args.topic, args.payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/scripts/experience.py skills/experience-memory/tests/test_experience.py
git commit -m "Add claim posts with stance validation and distill-ready threshold

Non-NEW stances must cite an existing post in the thread; this is the
disagreement-as-signal mechanism from the knowledge-centric protocol."
```

---

### Task 4: `thread` and `bundle` commands

**Files:**
- Modify: `skills/experience-memory/scripts/experience.py`
- Test: `skills/experience-memory/tests/test_experience.py`

**Interfaces:**
- Consumes: Task 1-3 helpers.
- Produces: `cmd_thread(store, slug)`, `cmd_bundle(store, slug, global_: bool)`. `bundle` output ends with the influence footer line beginning `influence:`. Task 5 writes the `bundle.md` files these read.

- [ ] **Step 1: Write the failing tests**

Add to `test_experience.py`:

```python
class TestThreadAndBundle(StoreTestCase):
    def seed_with_posts(self, slug="topic-a", n=2):
        self.create_topic(slug)
        run_cli(self.store, "attempt", slug, "--json", json.dumps(VALID_ATTEMPT))
        for _ in range(n):
            run_cli(self.store, "post", slug, "--json", json.dumps(valid_post()))
        return slug

    def test_thread_prints_attempts_and_posts(self):
        slug = self.seed_with_posts(n=2)
        code, out, _ = run_cli(self.store, "thread", slug)
        self.assertEqual(code, 0)
        self.assertIn("## Attempts", out)
        self.assertIn("## Posts", out)
        self.assertIn("Cold-onboard dev stack 1729", out)
        self.assertIn('"id": 2', out)
        self.assertIn("distilled through post 0", out)

    def test_bundle_missing_is_helpful_error(self):
        slug = self.seed_with_posts()
        code, _, err = run_cli(self.store, "bundle", slug)
        self.assertEqual(code, 2)
        self.assertIn("no bundle yet", err)

    def test_bundle_prints_content_and_influence_footer(self):
        slug = self.seed_with_posts()
        bundle_path = self.store / "topics" / slug / "bundle.md"
        bundle_path.write_text("## Transferable insights\ncontent here\n")
        code, out, _ = run_cli(self.store, "bundle", slug)
        self.assertEqual(code, 0)
        self.assertIn("content here", out)
        self.assertIn("influence:", out)

    def test_global_bundle_missing_is_helpful_error(self):
        code, _, err = run_cli(self.store, "bundle", "--global")
        self.assertEqual(code, 2)
        self.assertIn("no global bundle", err)

    def test_bundle_requires_topic_or_global(self):
        code, _, err = run_cli(self.store, "bundle")
        self.assertEqual(code, 2)
        self.assertIn("topic slug or --global", err)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/experience-memory && python3 -m unittest tests.test_experience.TestThreadAndBundle -v`
Expected: FAIL (argparse: invalid choice 'thread').

- [ ] **Step 3: Write the implementation**

Add to `experience.py` after `cmd_post`:

```python
def cmd_thread(store, slug):
    meta = load_topic(store, slug)
    print(f"# {meta['title']} ({slug})")
    print(f"distilled through post {meta.get('distilled_through_post_id', 0)}")
    print("\n## Attempts")
    for a in topic_attempts(store, slug):
        print(json.dumps(a, ensure_ascii=False, indent=2))
    print("\n## Posts")
    for p in topic_posts(store, slug):
        print(json.dumps(p, ensure_ascii=False, indent=2))


def cmd_bundle(store, slug, global_):
    if global_:
        path = store / "global" / "bundle.md"
        if not path.is_file():
            raise StoreError("no global bundle yet; run the cross-topic distill flow first")
    else:
        load_topic(store, slug)
        path = topic_dir(store, slug) / "bundle.md"
        if not path.is_file():
            raise StoreError(
                f"topic '{slug}' has no bundle yet; run the distill flow "
                "once the thread has posts")
    print(path.read_text(encoding="utf-8"))
    print('influence: when capturing this session, set "bundle_used": true '
          "on the attempt record")
```

Add the subparsers in `build_parser()`:

```python
    sp = sub.add_parser("thread", help="print a topic's attempts and posts")
    sp.add_argument("topic")

    sp = sub.add_parser("bundle", help="print a distilled bundle")
    sp.add_argument("topic", nargs="?")
    sp.add_argument("--global", action="store_true", dest="global_",
                    help="print the cross-topic principles bundle")
```

Add the dispatch branches in `main()`:

```python
        elif args.command == "thread":
            cmd_thread(store, args.topic)
        elif args.command == "bundle":
            if not args.global_ and not args.topic:
                raise StoreError("bundle requires a topic slug or --global")
            cmd_bundle(store, args.topic, args.global_)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/scripts/experience.py skills/experience-memory/tests/test_experience.py
git commit -m "Add thread and bundle read commands

thread is what makes capture-time stances possible; bundle is the pull
path for fresh sessions and carries the influence footer."
```

---

### Task 5: `distill` command — validation, lock, watermark, cross-topic

**Files:**
- Modify: `skills/experience-memory/scripts/experience.py`
- Test: `skills/experience-memory/tests/test_experience.py`

**Interfaces:**
- Consumes: Task 1-4 helpers.
- Produces: `validate_bundle_text(text: str) -> None`, `acquire_lock(tdir: Path) -> Path`, `cmd_distill(store, slug, bundle_file, hook, cross)`. After distill, `topic.json`'s `distilled_through_post_id` equals the max post id and `index.md` is regenerated.

- [ ] **Step 1: Write the failing tests**

Add to `test_experience.py`:

```python
VALID_BUNDLE = """## Transferable insights
- Set GCOM_PROXY_URL before first run (post 1)

## Confirmed constraints
- model-builder reads GCOM_PROXY_URL at startup only (post 1)

## Rejected hypotheses
- FALSIFIED: restarting mid-onboard recovers tenant resolution (post 2)

## Pitfalls
- Silent 'gcom client disabled' log line is the only symptom (post 1)

## Checks
- Check FalkorDB node counts after onboarding (attempt 1)

## Next steps
- Try var set from the start on a fresh stack
"""


class TestDistill(StoreTestCase):
    def seed_ready(self, slug="topic-a"):
        self.create_topic(slug)
        run_cli(self.store, "attempt", slug, "--json", json.dumps(VALID_ATTEMPT))
        for _ in range(5):
            run_cli(self.store, "post", slug, "--json", json.dumps(valid_post()))
        return slug

    def write_bundle_file(self, text=VALID_BUNDLE):
        p = self.store / "new-bundle.md"
        p.write_text(text)
        return p

    def test_distill_swaps_bundle_and_advances_watermark(self):
        slug = self.seed_ready()
        code, out, err = run_cli(self.store, "distill", slug,
                                 "--bundle-file", str(self.write_bundle_file()))
        self.assertEqual(code, 0, err)
        self.assertIn("distilled through post 5", out)
        meta = json.loads(
            (self.store / "topics" / slug / "topic.json").read_text())
        self.assertEqual(meta["distilled_through_post_id"], 5)
        self.assertIn("Transferable insights",
                      (self.store / "topics" / slug / "bundle.md").read_text())
        index = (self.store / "index.md").read_text()
        self.assertIn("bundle fresh", index)
        self.assertNotIn("distill ready", index)

    def test_distill_rejects_missing_section(self):
        slug = self.seed_ready()
        bad = VALID_BUNDLE.replace("## Pitfalls", "## Gotchas")
        code, _, err = run_cli(self.store, "distill", slug,
                               "--bundle-file", str(self.write_bundle_file(bad)))
        self.assertEqual(code, 2)
        self.assertIn("Pitfalls", err)

    def test_distill_rejects_out_of_order_sections(self):
        slug = self.seed_ready()
        bad = VALID_BUNDLE.replace(
            "## Transferable insights", "## ZZZ", 1).replace(
            "## Next steps", "## Transferable insights", 1)
        code, _, err = run_cli(self.store, "distill", slug,
                               "--bundle-file", str(self.write_bundle_file(bad)))
        self.assertEqual(code, 2)

    def test_distill_updates_hook_when_given(self):
        slug = self.seed_ready()
        run_cli(self.store, "distill", slug, "--hook", "new sharper hook",
                "--bundle-file", str(self.write_bundle_file()))
        self.assertIn("new sharper hook", (self.store / "index.md").read_text())

    def test_distill_refuses_when_locked(self):
        slug = self.seed_ready()
        lock = self.store / "topics" / slug / ".distill.lock"
        lock.write_text("12345")
        code, _, err = run_cli(self.store, "distill", slug,
                               "--bundle-file", str(self.write_bundle_file()))
        self.assertEqual(code, 2)
        self.assertIn("in progress", err)

    def test_distill_breaks_stale_lock(self):
        slug = self.seed_ready()
        lock = self.store / "topics" / slug / ".distill.lock"
        lock.write_text("12345")
        old = experience.time.time() - experience.LOCK_STALE_SECONDS - 10
        experience.os.utime(lock, (old, old))
        code, _, err = run_cli(self.store, "distill", slug,
                               "--bundle-file", str(self.write_bundle_file()))
        self.assertEqual(code, 0, err)

    def test_distill_cross_writes_global_bundle(self):
        code, out, err = run_cli(self.store, "distill", "--cross",
                                 "--bundle-file", str(self.write_bundle_file()))
        self.assertEqual(code, 0, err)
        self.assertIn("global bundle updated", out)
        self.assertTrue((self.store / "global" / "bundle.md").is_file())
        self.assertIn("- global —", (self.store / "index.md").read_text())

    def test_distill_requires_topic_or_cross(self):
        code, _, err = run_cli(self.store, "distill",
                               "--bundle-file", str(self.write_bundle_file()))
        self.assertEqual(code, 2)
        self.assertIn("topic slug or --cross", err)

    def test_oversize_bundle_warns_but_succeeds(self):
        slug = self.seed_ready()
        big = VALID_BUNDLE + "\n".join(f"- filler line {i}" for i in range(160))
        code, _, err = run_cli(self.store, "distill", slug,
                               "--bundle-file", str(self.write_bundle_file(big)))
        self.assertEqual(code, 0)
        self.assertIn("exceeds", err)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/experience-memory && python3 -m unittest tests.test_experience.TestDistill -v`
Expected: FAIL (argparse: invalid choice 'distill').

- [ ] **Step 3: Write the implementation**

Add to `experience.py` after `cmd_bundle`:

```python
def validate_bundle_text(text):
    positions = []
    for section in BUNDLE_SECTIONS:
        idx = text.find(section)
        if idx == -1:
            raise StoreError(f"bundle is missing required section '{section}'")
        positions.append(idx)
    if positions != sorted(positions):
        raise StoreError(
            "bundle sections are out of order; expected: " + ", ".join(BUNDLE_SECTIONS))
    if len(text.splitlines()) > BUNDLE_SIZE_WARN_LINES:
        print(f"warning: bundle exceeds {BUNDLE_SIZE_WARN_LINES} lines; "
              "distillation should prioritize harder", file=sys.stderr)


def acquire_lock(tdir):
    lock = tdir / ".distill.lock"
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        if age < LOCK_STALE_SECONDS:
            raise StoreError(
                f"distill already in progress for this topic (lock age {int(age)}s); "
                "retry later or remove the stale .distill.lock")
        lock.unlink()
    lock.write_text(str(os.getpid()))
    return lock


def cmd_distill(store, slug, bundle_file, hook, cross):
    bundle_path = Path(bundle_file)
    if not bundle_path.is_file():
        raise StoreError(f"bundle file not found: {bundle_file}")
    text = bundle_path.read_text(encoding="utf-8")
    validate_bundle_text(text)
    if cross:
        write_atomic(store / "global" / "bundle.md", text)
        regenerate_index(store)
        print("global bundle updated")
        return
    meta = load_topic(store, slug)
    tdir = topic_dir(store, slug)
    lock = acquire_lock(tdir)
    try:
        write_atomic(tdir / "bundle.md", text)
        posts = topic_posts(store, slug)
        meta["distilled_through_post_id"] = max(
            (p.get("id", 0) for p in posts), default=0)
        if hook:
            meta["hook"] = hook
        write_json_atomic(tdir / "topic.json", meta)
    finally:
        lock.unlink(missing_ok=True)
    regenerate_index(store)
    print(f"bundle for '{slug}' updated; "
          f"distilled through post {meta['distilled_through_post_id']}")
```

Add the subparser in `build_parser()`:

```python
    sp = sub.add_parser("distill",
                        help="install a new bundle written by the distiller")
    sp.add_argument("topic", nargs="?")
    sp.add_argument("--bundle-file", required=True)
    sp.add_argument("--hook", help="update the topic's one-line index hook")
    sp.add_argument("--cross", action="store_true",
                    help="update the global cross-topic bundle instead")
```

Add the dispatch branch in `main()`:

```python
        elif args.command == "distill":
            if not args.cross and not args.topic:
                raise StoreError("distill requires a topic slug or --cross")
            cmd_distill(store, args.topic, args.bundle_file, args.hook, args.cross)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/scripts/experience.py skills/experience-memory/tests/test_experience.py
git commit -m "Add distill command: validated atomic bundle swap with watermark

Posts are never mutated; the distilled_through_post_id watermark in
topic.json defines the undistilled count. A lock file guards the one
real race (two distills of the same topic)."
```

---

### Task 6: Stop-hook decision logic

**Files:**
- Create: `skills/experience-memory/scripts/stop_hook.py`
- Test: `skills/experience-memory/tests/test_stop_hook.py`

**Interfaces:**
- Consumes: nothing from `experience.py` (deliberately independent so a CLI bug can never break the hook).
- Produces: `should_fire(event: dict, store_dir: Path, marker_dir: Path) -> bool` (writes the marker as a side effect when returning True), `count_tool_uses(transcript_path: str) -> int`, `main() -> int` (reads event JSON on stdin; prints a `{"decision": "block", "reason": ...}` JSON line when firing; always returns 0). Task 7's `capture-reminder.sh` execs this file.

- [ ] **Step 1: Write the failing tests**

Create `skills/experience-memory/tests/test_stop_hook.py`:

```python
"""Tests for the Stop-hook decision logic."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("stop_hook", SCRIPTS / "stop_hook.py")
stop_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stop_hook)


class StopHookTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = self.tmp / "store"
        self.store.mkdir()
        self.markers = self.store / "markers"

    def make_event(self, tool_uses=20, session="s1", stop_active=False):
        transcript = self.tmp / f"transcript-{session}.jsonl"
        line = json.dumps(
            {"type": "assistant",
             "message": {"content": [{"type": "tool_use", "name": "Bash"}]}})
        transcript.write_text("\n".join([line] * tool_uses))
        return {"session_id": session, "transcript_path": str(transcript),
                "stop_hook_active": stop_active}

    def test_fires_on_substantive_session(self):
        self.assertTrue(stop_hook.should_fire(
            self.make_event(tool_uses=20), self.store, self.markers))

    def test_does_not_fire_twice_for_same_session(self):
        event = self.make_event(tool_uses=20)
        self.assertTrue(stop_hook.should_fire(event, self.store, self.markers))
        self.assertFalse(stop_hook.should_fire(event, self.store, self.markers))

    def test_does_not_fire_below_threshold(self):
        self.assertFalse(stop_hook.should_fire(
            self.make_event(tool_uses=5), self.store, self.markers))

    def test_does_not_fire_when_stop_hook_active(self):
        self.assertFalse(stop_hook.should_fire(
            self.make_event(tool_uses=20, stop_active=True),
            self.store, self.markers))

    def test_does_not_fire_when_store_missing(self):
        self.assertFalse(stop_hook.should_fire(
            self.make_event(tool_uses=20),
            self.tmp / "no-such-store", self.markers))

    def test_does_not_fire_on_missing_transcript(self):
        event = {"session_id": "s2", "transcript_path": str(self.tmp / "nope.jsonl"),
                 "stop_hook_active": False}
        self.assertFalse(stop_hook.should_fire(event, self.store, self.markers))

    def test_count_tool_uses_handles_spaced_json(self):
        transcript = self.tmp / "spaced.jsonl"
        transcript.write_text('{"type": "tool_use"}\n{"type":"tool_use"}\n')
        self.assertEqual(stop_hook.count_tool_uses(str(transcript)), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/experience-memory && python3 -m unittest tests.test_stop_hook -v`
Expected: FAIL at import time (`FileNotFoundError` for `scripts/stop_hook.py`).

- [ ] **Step 3: Write the implementation**

Create `skills/experience-memory/scripts/stop_hook.py`:

```python
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
```

Note the deviation from the spec recorded here deliberately: markers live in `<store>/markers/` rather than the session scratchpad, because the hook process does not reliably know the scratchpad path. Same intent (one reminder per session), more reliable location. `regenerate_index` and `iter_topic_metas` only read `topics/`, so the markers directory never leaks into the index.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/experience-memory && python3 -m unittest discover -s tests -v`
Expected: PASS (all, both test files).

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/scripts/stop_hook.py skills/experience-memory/tests/test_stop_hook.py
git commit -m "Add Stop-hook logic for one-shot capture reminders

Fires only for substantive sessions (tool-use count over threshold),
at most once per session via a marker file, and silently never when
the store is absent so the feature stays opt-in."
```

---

### Task 7: Hook wrappers and plugin registration

**Files:**
- Create: `hooks/hooks.json` (plugin root = repo root)
- Create: `hooks/session-start.sh`
- Create: `hooks/capture-reminder.sh`

**Interfaces:**
- Consumes: `stop_hook.py` from Task 6; `index.md` produced by the Task 1 CLI.
- Produces: plugin-registered SessionStart and Stop hooks. `EXPERIENCE_STORE` env var overrides the store path in both (used by tests and the e2e walkthrough).

- [ ] **Step 1: Verify plugin layout**

Run: `ls .claude-plugin 2>/dev/null; ls plugin.json 2>/dev/null; cat .claude-plugin/plugin.json 2>/dev/null || cat plugin.json`
Expected: locate the plugin manifest. `hooks/hooks.json` at the plugin root is auto-discovered by Claude Code; if the manifest has an explicit `"hooks"` field pointing elsewhere, place the file at that path instead and adjust the paths below.

- [ ] **Step 2: Write `hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/capture-reminder.sh"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Write `hooks/session-start.sh`**

```bash
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
```

- [ ] **Step 4: Write `hooks/capture-reminder.sh`**

```bash
#!/usr/bin/env bash
# experience-memory: one-shot capture reminder on Stop. All logic lives
# in stop_hook.py; this wrapper only resolves the path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/../skills/experience-memory/scripts/stop_hook.py"
```

- [ ] **Step 5: Make wrappers executable and verify manually**

```bash
chmod +x hooks/session-start.sh hooks/capture-reminder.sh
# Stop hook: garbage stdin must produce no output and exit 0
echo 'not json' | ./hooks/capture-reminder.sh; echo "exit=$?"
# Stop hook: substantive fixture must emit a block decision once, then stay quiet
export EXPERIENCE_STORE=/tmp/em-hooktest && mkdir -p "$EXPERIENCE_STORE"
python3 - <<'EOF'
import json
line = json.dumps({"type": "tool_use"})
open("/tmp/em-transcript.jsonl", "w").write("\n".join([line] * 20))
EOF
echo '{"session_id":"manual-1","transcript_path":"/tmp/em-transcript.jsonl","stop_hook_active":false}' | ./hooks/capture-reminder.sh
echo '{"session_id":"manual-1","transcript_path":"/tmp/em-transcript.jsonl","stop_hook_active":false}' | ./hooks/capture-reminder.sh
# SessionStart: no index -> no output; with index -> wrapped content
./hooks/session-start.sh
python3 skills/experience-memory/scripts/experience.py --store "$EXPERIENCE_STORE" create demo-topic --title "Demo" --hook "demo hook"
./hooks/session-start.sh
rm -rf /tmp/em-hooktest /tmp/em-transcript.jsonl && unset EXPERIENCE_STORE
```

Expected: first capture-reminder call prints one `{"decision": "block", ...}` line, second prints nothing; session-start prints nothing before the topic exists and the wrapped index after.

- [ ] **Step 6: Commit**

```bash
git add hooks/hooks.json hooks/session-start.sh hooks/capture-reminder.sh
git commit -m "Register experience-memory plugin hooks

SessionStart injects the topic index; Stop emits a one-shot capture
reminder for substantive sessions. Both are silent no-ops until the
store exists, keeping the feature opt-in."
```

---

### Task 8: Distiller agent prompt and schema reference

**Files:**
- Create: `skills/experience-memory/agents/distiller.md`
- Create: `skills/experience-memory/references/schemas.md`

**Interfaces:**
- Consumes: thread output format from Task 4, bundle section contract from Task 5.
- Produces: the distiller prompt that SKILL.md (Task 9) dispatches as a subagent, and the schema reference the capture flow reads.

- [ ] **Step 1: Write `agents/distiller.md`**

```markdown
# Distiller

You are the distiller for an experience-memory store. You receive one
topic's full forum thread (attempt records and claim posts) and its
current bundle, and you produce a replacement bundle. You have no other
context, on purpose: judge claims only on the evidence cited in the
thread, never on plausibility or eloquence.

## Inputs

The dispatching agent gives you:

1. The topic slug and title.
2. The full thread: attempt records (JSON) and posts (JSON), in order.
3. The current bundle markdown (may be absent for a first distillation).

## Output contract

Return ONLY the new bundle markdown, nothing else. It must contain
exactly these six section headers, in this order:

    ## Transferable insights
    ## Confirmed constraints
    ## Rejected hypotheses
    ## Pitfalls
    ## Checks
    ## Next steps

Every entry must cite its sources like `(post 7)` or `(attempt 3)`.
Keep the whole bundle under 150 lines; prioritize rather than compress.

## Rules

1. **Selection, not summarization.** Keep claims that are actionable,
   evidence-grounded, and scoped to stated conditions. Drop vague or
   generic advice entirely (anything true of all software work, like
   "write tests" or "read the logs", does not belong here).
2. **Resolve stances.** A chain of AGREE posts with independent evidence
   promotes a claim toward Confirmed constraints. A DISAGREE backed by
   stronger evidence moves the losing claim to Rejected hypotheses,
   narrowed to the parameterization that was actually tested, with
   untried variants of the same family listed as UNTRIED. A genuine
   unresolved conflict keeps BOTH positions, each marked FALSIFIED or
   UNTRIED with its evidence. Never force consensus.
3. **Predictions are your strongest evidence.** Each post has a
   falsifiable predicted_outcome; later attempt records show how it
   fared. A confirmed prediction promotes the claim; a failed one
   demotes or narrows it. Say which when it decides an entry.
4. **Rebuild, do not append.** Start from the thread plus the current
   bundle and produce the best current view. Drop superseded guidance.
   Bundles must not grow monotonically.
5. **Scope every insight.** "X works" is not an entry; "X works when Y,
   evidenced by Z (post N)" is.

## Also return (after the bundle, on one final line)

A single line starting with `HOOK: ` giving a sharp one-line hook for
the topic index (concrete nouns, the gotchas, not a generic label).
The dispatching agent strips this line before installing the bundle.
```

- [ ] **Step 2: Write `references/schemas.md`**

```markdown
# experience-memory payload schemas

Reference for the capture flow. The CLI validates structure; the
quality bars below are enforced by you, the capturing agent, because
they are not mechanically checkable.

## Attempt record (`experience.py attempt <topic> --json '...'`)

    {
      "repo": "asserts-adi",                  // optional but recommended
      "branch": "fix/onboarding",             // optional
      "task": "one line: what was attempted",  // required
      "outcome": "solved",                     // required: solved | partial | failed | abandoned
      "verification": "how the outcome was determined",  // required, non-empty
      "bundle_used": true                      // optional bool: was a bundle pulled this session?
    }

Quality bar: `verification` names the check that was actually run
(test output, node counts, an alert clearing), not an impression.

## Post (`experience.py post <topic> --json '...'`)

    {
      "attempt_id": 4,                         // required; must exist in this topic
      "claim": "the insight itself, one or two sentences",
      "load_bearing_assumption": "names a SPECIFIC tool, API, file, or invariant",
      "evidence": "a 1-2 sentence quote from real trace or output",
      "stance": "NEW",                         // NEW | AGREE | DISAGREE | SYNTHESIZE
      "stance_post_id": null,                  // required post id for non-NEW stances
      "proposed_change": "one concrete change for the next session on this topic",
      "predicted_outcome": "a falsifiable prediction a future session can check",
      "confidence": "medium"                   // high | medium | low
    }

Quality bars (reject your own draft if it misses any):

- The assumption names something concrete. "the build is flaky" fails;
  "testcontainers maps port 5432 before the container is ready" passes.
- The evidence is a quote from actual output, not a paraphrase.
- The prediction is falsifiable: a future session could run something
  and observe it wrong.
- Before choosing NEW, read the thread. Evidence that bears on an
  existing claim is an AGREE, DISAGREE, or SYNTHESIZE with a citation,
  not a duplicate NEW post.
- Generic advice ("write tests first") is never a valid claim.

## Bundle sections (written by the distiller, installed via `distill`)

    ## Transferable insights   <- actionable, scoped, conditional guidance
    ## Confirmed constraints   <- verified environment or API requirements
    ## Rejected hypotheses     <- falsified approaches, with untried variants kept
    ## Pitfalls                <- recurring errors and their triggers
    ## Checks                  <- validation strategies that caught real problems
    ## Next steps              <- prioritized open questions

All six headers required, in this order. Entries cite `(post N)` or
`(attempt N)`. Target under 150 lines.
```

- [ ] **Step 3: Review against spec**

Check `docs/superpowers/specs/2026-07-29-experience-memory-design.md` sections "Distillation" and "Schemas": every distiller rule in the spec (selection not summarization, stance resolution, prediction-versus-outcome, no monotonic growth, size cap) appears in `distiller.md`; every schema field and prompt-enforced quality bar appears in `schemas.md`.

- [ ] **Step 4: Commit**

```bash
git add skills/experience-memory/agents/distiller.md skills/experience-memory/references/schemas.md
git commit -m "Add distiller prompt and payload schema reference

The distiller is deliberately context-free and judges claims on cited
evidence only; the schema reference carries the quality bars the CLI
cannot check mechanically."
```

---

### Task 9: SKILL.md — capture, pull, and distill flows

**Files:**
- Create: `skills/experience-memory/SKILL.md`

**Interfaces:**
- Consumes: every CLI command (Tasks 1-5), `agents/distiller.md` and `references/schemas.md` (Task 8), hook behavior (Tasks 6-7).
- Produces: the skill entry point that the plugin system auto-discovers.

- [ ] **Step 1: Write `skills/experience-memory/SKILL.md`**

```markdown
---
name: experience-memory
description: >
  Knowledge-centric self-improvement for local Claude Code work, adapted from
  arXiv 2607.19592. Maintains a global store (~/.experience-memory/) of
  topic-keyed forum threads: evidence-grounded claims with stances, typed
  attempt records, and distilled bundles that seed future sessions. Use this
  skill when: a Stop-hook reminder says the session was substantive and worth
  capturing; the user says "capture this session", "post experience",
  "remember what we learned", "what have we learned about X", or "distill
  topic X"; the SessionStart index shows a topic matching work about to start
  (pull the bundle first); or a topic is marked distill ready. Covers the
  capture flow (attempt record plus claims with stances), the pull flow
  (bundle retrieval before matching work), and the distill flow (subagent
  selection into a typed bundle).
---

# experience-memory

A local implementation of knowledge-centric self-improvement: sessions stay
disposable, and the artifact that improves is a curated knowledge store.
All store mutations go through the CLI; never edit store files by hand.

    CLI="$(dirname "$0")"  # from this skill dir: scripts/experience.py
    python3 <skill-dir>/scripts/experience.py <command> [args]
    # every command accepts --store <path>; default is ~/.experience-memory

Read `references/schemas.md` before writing any payload.

## Pull flow (start of matching work)

Trigger: the SessionStart index (an `<experience-memory-index>` block) lists
a topic matching the work about to start.

1. Run `experience.py bundle <topic-slug>` and read it as prior evidence.
2. Do not repeat Rejected hypotheses. If you believe this situation differs
   from the falsified conditions, say so explicitly; that sets up a DISAGREE
   post at capture time.
3. Run the bundle's Checks early; they caught real problems before.
4. Remember that a bundle was used: the capture-flow attempt record must set
   `"bundle_used": true`.

If the work is substantive but matches no topic, pull the global bundle:
`experience.py bundle --global` (skip silently if it does not exist yet).

## Capture flow (end of substantive work)

Trigger: the Stop-hook reminder, or the user asks to capture.

Worth capturing means hypotheses were tested or something non-obvious was
learned. Routine sessions with nothing generalizable are NOT captured; tell
the user so and stop. Never capture secrets, tokens, or customer data in any
field.

1. **Topic match.** Run `experience.py topics`. Match the session's work
   against existing topics; bias strongly toward reuse. Create a new topic
   only when nothing fits:
   `experience.py create <slug> --title "..." --hook "<concrete gotcha line>"
   --tags <repo>,<domain>`.
2. **Attempt record.** `experience.py attempt <slug> --json '<payload>'`
   per `references/schemas.md`. Outcome and verification are about what
   actually happened, including failures; set `bundle_used` truthfully.
3. **Read the thread.** `experience.py thread <slug>`. This step is
   mandatory before posting: stances against prior claims are the point of
   the system.
4. **Post 1 to 3 claims.** `experience.py post <slug> --json '<payload>'`.
   Apply every quality bar in `references/schemas.md`. If the CLI rejects a
   payload, fix the named field and retry.
5. **Relay the threshold.** If the CLI prints `distill ready`, tell the user
   and offer to run the distill flow now. Never distill without asking.

## Distill flow (on request or when a topic is distill ready)

1. Collect inputs: `experience.py thread <slug>` output and, if present,
   `experience.py bundle <slug>` output.
2. Dispatch a subagent (Sonnet tier; this is selection over a bounded
   thread, not hard reasoning). Its prompt is the full content of
   `agents/distiller.md` followed by the collected inputs. It returns the
   new bundle text plus a final `HOOK: ...` line.
3. Strip the HOOK line, write the bundle text to a temp file, then install:
   `experience.py distill <slug> --bundle-file <tmp> --hook "<hook text>"`.
4. If the CLI rejects the bundle (missing or out-of-order sections),
   re-dispatch the distiller once with the error appended; if it fails
   again, report the error and stop.
5. Confirm to the user: watermark position and one line on what changed in
   the bundle.

**Cross-topic distill** (user asks, roughly monthly): collect every topic's
`bundle.md` via `experience.py bundle <slug>` for each topic, dispatch the
distiller with all of them and the instruction that only principles
evidenced in two or more topics qualify, then install with
`experience.py distill --cross --bundle-file <tmp>`.

## Bootstrap

The store does not exist until the first `create`. Hooks are silent no-ops
until then, so the whole system is opt-in: the first capture creates it.
```

- [ ] **Step 2: Review against spec**

Check every flow in the spec ("Capture flow", "Injection and pull", "Distillation") has a matching section here, the trigger description covers the Stop-hook reminder and index-match cases, and no CLI command is referenced that does not exist in Tasks 1-5 (`create`, `topics`, `attempt`, `post`, `thread`, `bundle`, `distill`, `index`).

- [ ] **Step 3: Commit**

```bash
git add skills/experience-memory/SKILL.md
git commit -m "Add experience-memory SKILL.md orchestrating capture, pull, and distill

The skill owns judgment (what is worth capturing, topic matching,
stance discipline); the CLI owns integrity; hooks own timing."
```

---

### Task 10: Documentation, repo indexes, final verification

**Files:**
- Create: `skills/experience-memory/README.md`
- Create: `skills/experience-memory/CLAUDE.md`
- Modify: `README.md` (repo root, skills table)
- Modify: `CLAUDE.md` (repo root, "Current Skills" list)

**Interfaces:**
- Consumes: everything from Tasks 1-9.
- Produces: human docs, dev docs with the e2e walkthrough, updated repo indexes.

- [ ] **Step 1: Write `skills/experience-memory/README.md`**

```markdown
# experience-memory

Knowledge-centric self-improvement for local Claude Code work, adapted from
["Knowledge-Centric Self-Improvement" (arXiv 2607.19592)](https://arxiv.org/abs/2607.19592).

The idea, inverted from most self-improvement schemes: sessions stay
disposable, and the thing that improves is a curated knowledge store.
Sessions post evidence-grounded claims into per-topic forum threads, take
explicit stances (AGREE / DISAGREE / SYNTHESIZE) against earlier claims, and
a distiller periodically selects the survivors into a compact bundle that
seeds future sessions. Falsified approaches are kept as rejected hypotheses,
which is precisely the knowledge a plain lessons-learned log loses.

## How it works day to day

- **SessionStart**: a hook injects a one-line-per-topic index.
- **During work**: when the session matches a topic, Claude pulls the
  topic's bundle, avoids its rejected hypotheses, and runs its checks early.
- **Stop**: after a substantive session, a hook reminds Claude once to offer
  capture: an attempt record (outcome plus how it was verified) and one to
  three schema-validated claims with stances against the existing thread.
- **When a topic accumulates 5 undistilled posts**: it is marked distill
  ready; a fresh subagent rebuilds the bundle by selection, never
  summarization.

## Layout

Store: `~/.experience-memory/` (override with `--store` or the
`EXPERIENCE_STORE` env var for the hooks).

    topics/<slug>/{topic.json, attempts.jsonl, posts.jsonl, bundle.md}
    global/bundle.md    # cross-topic principles
    index.md            # injected at SessionStart

Everything is stdlib-only Python plus two small bash hook wrappers. The
store is opt-in: hooks stay silent until the first topic is created.

## Relationship to design-memory

design-memory (also in this repo) stores design *decisions*; this stores
tested *claims* with evidence and falsification. They are complementary
layers and share no infrastructure.
```

- [ ] **Step 2: Write `skills/experience-memory/CLAUDE.md`**

```markdown
# CLAUDE.md — experience-memory

## Architecture

Three layers with strict responsibilities:

- `scripts/experience.py` — the integrity boundary. All store mutations go
  through it: schema validation, appends, atomic bundle swaps, watermark,
  index regeneration. Append-only JSONL for attempts/posts; watermark
  (`distilled_through_post_id` in topic.json) instead of mutating posts.
- `scripts/stop_hook.py` + `hooks/` (plugin root) — timing. SessionStart
  injects `index.md`; Stop fires a one-shot reminder for substantive
  sessions (>15 tool uses, marker per session under `<store>/markers/`).
  Hooks always exit 0 and never print on internal error.
- `SKILL.md` + `agents/distiller.md` + `references/schemas.md` — judgment.
  What is worth capturing, topic matching, stance discipline, distillation
  rules (selection not summarization, stance resolution, prediction vs
  outcome, no monotonic growth).

Spec: `docs/superpowers/specs/2026-07-29-experience-memory-design.md`.

## Tests

    cd skills/experience-memory && python3 -m unittest discover -s tests -v

All tests run against temp-dir stores via `--store`; never the real store.

## End-to-end walkthrough (manual)

    export EXPERIENCE_STORE=/tmp/em-e2e && rm -rf "$EXPERIENCE_STORE"
    CLI="skills/experience-memory/scripts/experience.py"
    python3 $CLI --store "$EXPERIENCE_STORE" create flaky-ci-demo \
      --title "Flaky CI demo" --hook "testcontainers port races" --tags demo
    python3 $CLI --store "$EXPERIENCE_STORE" attempt flaky-ci-demo --json \
      '{"task":"fix flaky pg test","outcome":"failed","verification":"3 runs, 2 failures"}'
    python3 $CLI --store "$EXPERIENCE_STORE" post flaky-ci-demo --json \
      '{"attempt_id":1,"claim":"retry masks a port race","load_bearing_assumption":"testcontainers maps 5432 before ready","evidence":"log: connection refused then success on retry","stance":"NEW","stance_post_id":null,"proposed_change":"wait on readiness probe not sleep","predicted_outcome":"0 failures in 5 runs with probe","confidence":"medium"}'
    python3 $CLI --store "$EXPERIENCE_STORE" attempt flaky-ci-demo --json \
      '{"task":"retry with readiness probe","outcome":"solved","verification":"5 clean runs"}'
    python3 $CLI --store "$EXPERIENCE_STORE" post flaky-ci-demo --json \
      '{"attempt_id":2,"claim":"probe fixes it; sleep-based waits were the cause","load_bearing_assumption":"pg readiness = accepting connections, not container started","evidence":"5 clean runs after probe swap","stance":"AGREE","stance_post_id":1,"proposed_change":"apply probe pattern to redis tests too","predicted_outcome":"redis tests also stabilize with probe","confidence":"high"}'
    python3 $CLI --store "$EXPERIENCE_STORE" thread flaky-ci-demo
    # write a six-section bundle to /tmp/em-bundle.md by hand or via the
    # distiller prompt, then:
    python3 $CLI --store "$EXPERIENCE_STORE" distill flaky-ci-demo \
      --bundle-file /tmp/em-bundle.md --hook "pg port races: probe not sleep"
    python3 $CLI --store "$EXPERIENCE_STORE" bundle flaky-ci-demo
    cat "$EXPERIENCE_STORE/index.md"   # expect: bundle fresh, new hook
    rm -rf "$EXPERIENCE_STORE" && unset EXPERIENCE_STORE

Expected at each step: exit 0, and after distill the index shows
`bundle fresh` with the updated hook. To exercise a DISAGREE, add a third
post with `"stance":"DISAGREE","stance_post_id":1` and re-distill: the
losing claim should land under Rejected hypotheses, narrowed.

## Modification notes

- New post fields: add to `POST_REQUIRED_FIELDS` (or optional handling) in
  `experience.py`, to `references/schemas.md`, and to the tests. The store
  needs no migration for additive fields.
- Threshold and caps are constants at the top of `experience.py`
  (`DISTILL_THRESHOLD`, `BUNDLE_SIZE_WARN_LINES`) and `stop_hook.py`
  (`TOOL_USE_THRESHOLD`).
- Bundle section names are load-bearing in three places: `BUNDLE_SECTIONS`,
  `agents/distiller.md`, `references/schemas.md`. Change all or none.
```

- [ ] **Step 3: Update the repo indexes**

In root `README.md`, add a row to the skills table (match the existing table format exactly):

```markdown
| [experience-memory](skills/experience-memory/) | Knowledge-centric self-improvement (arXiv 2607.19592): topic-keyed threads of evidence-grounded claims with stances, distilled into bundles that seed future sessions via hooks. |
```

In root `CLAUDE.md`, add to "Current Skills" after design-memory:

```markdown
- **experience-memory** — Knowledge-centric self-improvement adapted from arXiv 2607.19592. A global store of topic-keyed forum threads (claims with AGREE/DISAGREE/SYNTHESIZE stances, typed attempt records) distilled into bundles that seed future sessions. Hook-prompted capture, index injection at SessionStart. Stdlib only. See `skills/experience-memory/CLAUDE.md`.
```

- [ ] **Step 4: Full verification**

```bash
cd skills/experience-memory && python3 -m unittest discover -s tests -v && cd ../..
bash -n hooks/session-start.sh hooks/capture-reminder.sh
python3 -c "import json; json.load(open('hooks/hooks.json'))"
```

Expected: all tests pass, both shell scripts parse, hooks.json is valid JSON. Then run the e2e walkthrough from CLAUDE.md once, end to end.

- [ ] **Step 5: Commit**

```bash
git add skills/experience-memory/README.md skills/experience-memory/CLAUDE.md README.md CLAUDE.md
git commit -m "Document experience-memory and add it to the repo indexes

README covers the day-to-day loop for humans; CLAUDE.md carries the
architecture boundaries, the e2e walkthrough, and modification notes."
```

---

## Self-Review Notes

- **Spec coverage:** store layout (Task 1), attempt/post schemas and validation (Tasks 2-3), thread/bundle reads with influence footer (Task 4), distill with watermark, lock, section validation, size warning, cross-topic (Task 5), Stop-hook substance gate with marker and silent failure (Task 6), SessionStart injection and plugin registration (Task 7), distiller rules and prompt-enforced quality bars (Task 8), capture/pull/distill orchestration and bootstrap opt-in (Task 9), docs, e2e, repo indexes (Task 10). Spec's error-handling section maps to: hooks exit 0 (Tasks 6-7), CLI as integrity boundary with helpful errors (Tasks 1-5), O_APPEND and atomic swap (Task 1), lock (Task 5), corrupt-line tolerance (Task 1).
- **Known deviation from spec, carried into code comments:** Stop-hook markers live under `<store>/markers/` instead of the session scratchpad (hook cannot reliably resolve the scratchpad path). Recorded in Task 6.
- **Type consistency check:** `cmd_*` signatures, `POST_REQUIRED_FIELDS`, `BUNDLE_SECTIONS`, and constant names match across all tasks; `stance_post_id` is `None` for NEW everywhere; `--store` accepted globally; exit codes 0/2 uniform.
