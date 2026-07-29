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
