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


if __name__ == "__main__":
    unittest.main()
