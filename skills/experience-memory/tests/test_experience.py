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
