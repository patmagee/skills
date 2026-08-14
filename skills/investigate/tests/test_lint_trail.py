"""Tests for the investigate trail linter."""
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
