import json
import os
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "claude-usage"

NOW = 1_800_000_000
HOUR = 3600


def load_script():
    # The command has no .py suffix, so the usual import machinery does not find it.
    loader = SourceFileLoader("claude_usage", str(SCRIPT))
    module = module_from_spec(spec_from_loader("claude_usage", loader))
    loader.exec_module(module)
    return module


claude_usage = load_script()


def payload(five_hour=None, seven_day=None):
    limits = {}
    if five_hour:
        limits["five_hour"] = {"used_percentage": five_hour[0], "resets_at": five_hour[1]}
    if seven_day:
        limits["seven_day"] = {"used_percentage": seven_day[0], "resets_at": seven_day[1]}
    return {"model": {"id": "claude"}, "rate_limits": limits} if limits else {"model": {"id": "claude"}}


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state" / "rate-limits.json"

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        return json.loads(self.path.read_text())

    def test_keeps_both_windows(self):
        claude_usage.record(payload((36.0, NOW + HOUR), (5.0, NOW + 100 * HOUR)), self.path, NOW)
        self.assertEqual(self.state(), {
            "windows": {
                "five_hour": {"used_percentage": 36.0, "resets_at": NOW + HOUR},
                "seven_day": {"used_percentage": 5.0, "resets_at": NOW + 100 * HOUR},
            },
            "recordedAt": NOW,
        })

    def test_payload_without_limits_marks_the_status_line_as_set_up(self):
        claude_usage.record(payload(), self.path, NOW)
        self.assertEqual(self.state(), {"windows": {}, "recordedAt": None})

    def test_payload_without_limits_keeps_earlier_readings(self):
        claude_usage.record(payload((36.0, NOW + HOUR)), self.path, NOW)
        claude_usage.record(payload(), self.path, NOW + 60)
        self.assertEqual(self.state()["windows"]["five_hour"]["used_percentage"], 36.0)

    def test_lower_reading_of_the_same_window_is_an_old_one(self):
        claude_usage.record(payload((40.0, NOW + HOUR)), self.path, NOW)
        claude_usage.record(payload((30.0, NOW + HOUR + 5)), self.path, NOW + 60)
        self.assertEqual(self.state()["windows"]["five_hour"]["used_percentage"], 40.0)
        self.assertEqual(self.state()["recordedAt"], NOW)

    def test_same_reading_again_refreshes_the_time(self):
        claude_usage.record(payload((40.0, NOW + HOUR)), self.path, NOW)
        claude_usage.record(payload((40.0, NOW + HOUR)), self.path, NOW + 60)
        self.assertEqual(self.state()["recordedAt"], NOW + 60)

    def test_new_window_replaces_the_old_one(self):
        claude_usage.record(payload((90.0, NOW + HOUR)), self.path, NOW)
        claude_usage.record(payload((2.0, NOW + 6 * HOUR)), self.path, NOW + 2 * HOUR)
        self.assertEqual(self.state()["windows"]["five_hour"], {"used_percentage": 2.0, "resets_at": NOW + 6 * HOUR})
        self.assertEqual(self.state()["recordedAt"], NOW + 2 * HOUR)

    def test_reading_from_an_older_window_is_ignored(self):
        claude_usage.record(payload((2.0, NOW + 6 * HOUR)), self.path, NOW)
        claude_usage.record(payload((90.0, NOW + HOUR)), self.path, NOW + 60)
        self.assertEqual(self.state()["windows"]["five_hour"]["used_percentage"], 2.0)

    def test_malformed_window_is_skipped(self):
        bad = {"rate_limits": {"five_hour": {"used_percentage": "x"}, "seven_day": {"used_percentage": 5, "resets_at": NOW + HOUR}}}
        claude_usage.record(bad, self.path, NOW)
        self.assertEqual(list(self.state()["windows"]), ["seven_day"])


class SummarizeTest(unittest.TestCase):
    def test_reports_the_window_closer_to_running_out(self):
        state = {
            "windows": {
                "five_hour": {"used_percentage": 36.5, "resets_at": NOW + HOUR},
                "seven_day": {"used_percentage": 5.0, "resets_at": NOW + 100 * HOUR},
            },
            "recordedAt": NOW - 60,
        }
        self.assertEqual(claude_usage.summarize(state, NOW), {
            "remainingPercent": 63,
            "windows": {
                "five_hour": {"remainingPercent": 63, "resetsAt": NOW + HOUR},
                "seven_day": {"remainingPercent": 95, "resetsAt": NOW + 100 * HOUR},
            },
            "recordedAt": NOW - 60,
        })

    def test_window_past_its_reset_is_full_again(self):
        state = {"windows": {"five_hour": {"used_percentage": 99.0, "resets_at": NOW - 1}}, "recordedAt": NOW - HOUR}
        summary = claude_usage.summarize(state, NOW)
        self.assertEqual(summary["windows"]["five_hour"], {"remainingPercent": 100, "resetsAt": None})
        self.assertEqual(summary["remainingPercent"], 100)

    def test_missing_state_means_not_set_up(self):
        with self.assertRaises(claude_usage.UsageError) as caught:
            claude_usage.summarize({}, NOW)
        self.assertEqual(caught.exception.code, "not_set_up")

    def test_state_without_windows_means_no_limits(self):
        with self.assertRaises(claude_usage.UsageError) as caught:
            claude_usage.summarize({"windows": {}, "recordedAt": None}, NOW)
        self.assertEqual(caught.exception.code, "no_limits")


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, XDG_STATE_HOME=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=""):
        return subprocess.run([str(SCRIPT), *args], input=stdin, env=self.env, capture_output=True, text=True, timeout=30)

    def test_record_prints_nothing_and_show_reads_it_back(self):
        recorded = self.run_cli("record", stdin=json.dumps(payload((36.0, 4_000_000_000), (5.0, 4_000_000_000))))
        self.assertEqual((recorded.returncode, recorded.stdout), (0, ""))
        shown = self.run_cli()
        self.assertEqual(shown.returncode, 0)
        self.assertEqual(json.loads(shown.stdout)["remainingPercent"], 64)

    def test_record_ignores_garbage(self):
        recorded = self.run_cli("record", stdin="not json")
        self.assertEqual((recorded.returncode, recorded.stdout), (0, ""))

    def test_show_without_state(self):
        shown = self.run_cli()
        self.assertEqual(shown.returncode, 1)
        self.assertEqual(json.loads(shown.stdout), {"error": "not_set_up"})


if __name__ == "__main__":
    unittest.main()
