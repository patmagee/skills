"""Tests for the investigate trail linter."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SAMPLE = SKILL_DIR / "references" / "sample-trail.md"


def load_module():
    path = SKILL_DIR / "scripts" / "lint_trail.py"
    spec = importlib.util.spec_from_file_location("lint_trail", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint_trail = load_module()


class ParseFrontmatterTest(unittest.TestCase):
    def test_reads_flat_keys_and_returns_remaining_body(self):
        meta, body = lint_trail.parse_frontmatter(
            "---\nsubject: a thing\nstatus: open\n---\n# Title\n"
        )
        self.assertEqual(meta["subject"], "a thing")
        self.assertEqual(meta["status"], "open")
        self.assertTrue(body.startswith("# Title"))

    def test_missing_frontmatter_yields_empty_metadata(self):
        meta, body = lint_trail.parse_frontmatter("# Title\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "# Title\n")


class SplitSectionsTest(unittest.TestCase):
    def test_finds_every_level_two_heading_in_the_sample(self):
        meta, body = lint_trail.parse_frontmatter(SAMPLE.read_text())
        sections = lint_trail.split_sections(body)
        self.assertIn("Findings", sections)
        self.assertIn("Evidence", sections)
        self.assertIn("Not checked", sections)
        self.assertIn("Synthesis", sections)


class ParseTableTest(unittest.TestCase):
    def test_drops_header_and_separator_rows(self):
        rows = lint_trail.parse_table(
            "| id | state |\n|----|-------|\n| F1 | open |\n"
        )
        self.assertEqual(rows, [["F1", "open"]])

    def test_reads_every_finding_row_from_the_sample(self):
        meta, body = lint_trail.parse_frontmatter(SAMPLE.read_text())
        rows = lint_trail.parse_table(lint_trail.split_sections(body)["Findings"])
        self.assertEqual([r[0] for r in rows], ["F1", "F2", "F3", "F4"])
        self.assertEqual(rows[3][3], "")


class ParseEvidenceTest(unittest.TestCase):
    def test_reads_records_and_preserves_id_order(self):
        meta, body = lint_trail.parse_frontmatter(SAMPLE.read_text())
        records, ids = lint_trail.parse_evidence(
            lint_trail.split_sections(body)["Evidence"]
        )
        self.assertEqual(ids, ["E1", "E2", "E3"])
        self.assertEqual(records["E1"]["form"], "metrics")
        self.assertEqual(records["E3"]["replayable"], "drifts")

    def test_repeated_id_appears_twice_in_the_id_list(self):
        records, ids = lint_trail.parse_evidence(
            "### E1\n\n- form: link\n\n### E1\n\n- form: link\n"
        )
        self.assertEqual(ids, ["E1", "E1"])


VALID = SAMPLE


def trail(findings, evidence, status="open", synthesis="", ledger=True):
    """Build a minimal trail body for a single check under test."""
    parts = [
        "---",
        "subject: test",
        "started: 2026-08-14T00:00Z",
        f"status: {status}",
        "trail-version: 1",
        "---",
        "",
        "# Test",
        "",
        "## Findings",
        "",
        "| id | claim | state | evidence | framed by |",
        "|----|-------|-------|----------|-----------|",
    ]
    parts.extend(findings)
    parts.extend(["", "## Evidence", ""])
    parts.extend(evidence)
    if ledger:
        parts.extend(
            [
                "",
                "## Not checked",
                "",
                "| what | why | noted |",
                "|------|-----|-------|",
                "| a thing | a reason | 2026-08-14T00:00Z |",
            ]
        )
    parts.extend(["", "## Synthesis", "", synthesis])
    return "\n".join(parts) + "\n"


GOOD_EVIDENCE = [
    "### E1",
    "",
    "- form: link",
    "- url: `https://example.invalid/d/abc`",
    "- points_at: the graph latency dashboard",
    "- replayable: yes",
]


class LintValidTrailTest(unittest.TestCase):
    def test_sample_trail_has_no_problems(self):
        self.assertEqual(lint_trail.lint(VALID.read_text()), [])


class LintFindingsTest(unittest.TestCase):
    def test_rejects_an_unknown_state(self):
        text = trail(["| F1 | a claim | probably | E1 | human |"], GOOD_EVIDENCE)
        self.assertIn("F1", " ".join(lint_trail.lint(text)))
        self.assertIn("probably", " ".join(lint_trail.lint(text)))

    def test_rejects_a_non_open_finding_with_no_evidence(self):
        text = trail(["| F1 | a claim | reasoned |  | human |"], GOOD_EVIDENCE)
        self.assertIn("cites no evidence", " ".join(lint_trail.lint(text)))

    def test_allows_an_open_finding_with_no_evidence(self):
        text = trail(["| F1 | a question | open |  | human |"], GOOD_EVIDENCE)
        self.assertEqual(lint_trail.lint(text), [])

    def test_rejects_a_citation_of_an_undefined_evidence_id(self):
        text = trail(["| F1 | a claim | reasoned | E9 | human |"], GOOD_EVIDENCE)
        self.assertIn("E9", " ".join(lint_trail.lint(text)))

    def test_rejects_an_unknown_framed_by_value(self):
        text = trail(["| F1 | a claim | reasoned | E1 | the dog |"], GOOD_EVIDENCE)
        self.assertIn("framed by", " ".join(lint_trail.lint(text)))


class LintEvidenceTest(unittest.TestCase):
    def test_rejects_a_duplicate_evidence_id(self):
        text = trail(
            ["| F1 | a claim | reasoned | E1 | human |"],
            GOOD_EVIDENCE + [""] + GOOD_EVIDENCE,
        )
        self.assertIn("duplicate", " ".join(lint_trail.lint(text)))

    def test_rejects_an_unknown_form(self):
        evidence = ["### E1", "", "- form: vibes", "- replayable: yes"]
        text = trail(["| F1 | a claim | reasoned | E1 | human |"], evidence)
        self.assertIn("vibes", " ".join(lint_trail.lint(text)))

    def test_rejects_a_missing_required_key_for_the_form(self):
        evidence = [
            "### E1",
            "",
            "- form: metrics",
            "- target: `grafanacloud-prom`",
            "- query: `up`",
            "- replayable: yes",
            "- returned:",
        ]
        text = trail(["| F1 | a claim | reasoned | E1 | human |"], evidence)
        self.assertIn("window", " ".join(lint_trail.lint(text)))

    def test_rejects_an_unknown_replayable_value(self):
        evidence = [
            "### E1",
            "",
            "- form: link",
            "- url: `https://example.invalid/`",
            "- points_at: a dashboard",
            "- replayable: maybe",
        ]
        text = trail(["| F1 | a claim | reasoned | E1 | human |"], evidence)
        self.assertIn("maybe", " ".join(lint_trail.lint(text)))

    def test_accepts_an_empty_returned_value_because_content_may_be_fenced(self):
        evidence = [
            "### E1",
            "",
            "- form: metrics",
            "- target: `grafanacloud-prom`",
            "- query: `up`",
            "- window: `2026-08-14T00:00:00Z` to `2026-08-14T01:00:00Z`",
            "- replayable: yes",
            "- returned:",
        ]
        text = trail(["| F1 | a claim | reasoned | E1 | human |"], evidence)
        self.assertEqual(lint_trail.lint(text), [])


class LintSectionsTest(unittest.TestCase):
    def test_rejects_a_missing_gap_ledger(self):
        text = trail(
            ["| F1 | a claim | reasoned | E1 | human |"], GOOD_EVIDENCE, ledger=False
        )
        self.assertIn("Not checked", " ".join(lint_trail.lint(text)))

    def test_rejects_a_closed_trail_with_an_empty_synthesis(self):
        text = trail(
            ["| F1 | a claim | reasoned | E1 | human |"], GOOD_EVIDENCE, status="closed"
        )
        self.assertIn("synthesis", " ".join(lint_trail.lint(text)))

    def test_allows_an_open_trail_with_an_empty_synthesis(self):
        text = trail(["| F1 | a claim | reasoned | E1 | human |"], GOOD_EVIDENCE)
        self.assertEqual(lint_trail.lint(text), [])


class MainTest(unittest.TestCase):
    """main() prints, so capture stdout or its output looks like a test failure."""

    def run_main(self, *paths):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = lint_trail.main([str(p) for p in paths])
        return code, buffer.getvalue()

    def test_returns_zero_for_the_sample_trail(self):
        code, output = self.run_main(VALID)
        self.assertEqual(code, 0)
        self.assertIn("ok", output)

    def test_returns_one_for_a_broken_trail(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.md"
            broken.write_text(
                trail(["| F1 | a claim | reasoned |  | human |"], GOOD_EVIDENCE)
            )
            code, output = self.run_main(broken)
        self.assertEqual(code, 1)
        self.assertIn("cites no evidence", output)


if __name__ == "__main__":
    unittest.main()
