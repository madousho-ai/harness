#!/usr/bin/env python3
"""Tests for the tasks.md parser.

Run from the extension root:

    python3 -m unittest discover -s tests -t .
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "python"))

import waves  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-tasks.md"


class ParseWavesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = FIXTURE.read_text(encoding="utf-8")
        cls.waves = waves.parse_tasks(cls.text)

    def wave(self, wave_id: str) -> waves.Wave:
        for item in self.waves:
            if item.id == wave_id:
                return item
        self.fail(f"no wave {wave_id} in {[w.id for w in self.waves]}")

    def test_one_wave_per_phase_heading(self):
        self.assertEqual([w.id for w in self.waves], ["W1", "W2", "W3", "W4", "W5"])
        self.assertEqual([w.phase for w in self.waves], [1, 2, 3, 4, 5])

    def test_titles_come_from_the_heading(self):
        self.assertEqual(self.wave("W1").title, "Setup")
        self.assertTrue(self.wave("W3").title.startswith("User Story 1 — Publish a widget"))

    def test_headings_inside_a_backtick_fence_are_not_waves(self):
        titles = " ".join(w.title for w in self.waves)
        self.assertNotIn("inside a fence", titles)
        self.assertNotIn(99, [w.phase for w in self.waves])

    def test_headings_inside_a_tilde_fence_are_not_waves(self):
        self.assertNotIn(98, [w.phase for w in self.waves])

    def test_task_lines_inside_a_fence_are_not_collected(self):
        every_id = {task.id for w in self.waves for task in w.tasks}
        self.assertNotIn("T900", every_id)
        self.assertNotIn("T901", every_id)

    def test_task_lines_outside_every_phase_are_not_collected(self):
        every_id = {task.id for w in self.waves for task in w.tasks}
        self.assertNotIn("T902", every_id)

    def test_tasks_are_grouped_by_phase(self):
        self.assertEqual([t.id for t in self.wave("W1").tasks], ["T001", "T002"])
        self.assertEqual([t.id for t in self.wave("W2").tasks], ["T003", "T004", "T005"])
        self.assertEqual([t.id for t in self.wave("W3").tasks], ["T006", "T007"])
        self.assertEqual([t.id for t in self.wave("W4").tasks], ["T008"])
        self.assertEqual([t.id for t in self.wave("W5").tasks], ["T009"])

    def test_checkbox_state_is_read(self):
        self.assertTrue(all(t.done for t in self.wave("W1").tasks))
        self.assertFalse(any(t.done for t in self.wave("W2").tasks))

    def test_parallel_marker_is_read(self):
        by_id = {t.id: t for t in self.wave("W2").tasks}
        self.assertTrue(by_id["T004"].parallel)
        self.assertFalse(by_id["T003"].parallel)

    def test_stories_come_from_the_heading_and_from_inline_tags(self):
        self.assertEqual(self.wave("W3").stories, ["US1"])
        self.assertEqual(self.wave("W4").stories, ["US2"])
        self.assertEqual(self.wave("W1").stories, [])
        self.assertEqual({t.id: t.stories for t in self.wave("W3").tasks}["T006"], ["US1"])

    def test_status_is_derived_from_the_checkboxes(self):
        self.assertEqual(self.wave("W1").status, "PASS")
        self.assertEqual(self.wave("W2").status, "PENDING")

    def test_partial_is_distinct_from_pending(self):
        text = self.text.replace(
            "- [ ] T003 Add the `WidgetId`", "- [X] T003 Add the `WidgetId`"
        )
        parsed = {w.id: w for w in waves.parse_tasks(text)}
        self.assertEqual(parsed["W2"].status, "PARTIAL")

    def test_next_wave_is_the_first_that_is_not_finished(self):
        self.assertEqual(waves.next_wave(self.waves).id, "W2")


class WaveSectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = FIXTURE.read_text(encoding="utf-8")
        cls.waves = {w.id: w for w in waves.parse_tasks(cls.text)}

    def test_section_carries_the_subheadings_and_the_tasks(self):
        section = waves.wave_section_text(self.text, self.waves["W2"])
        self.assertIn("## Phase 2: Foundational", section)
        self.assertIn("### The column types", section)
        self.assertIn("T003", section)
        self.assertIn("T005", section)

    def test_section_stops_at_the_next_phase(self):
        section = waves.wave_section_text(self.text, self.waves["W2"])
        self.assertNotIn("T006", section)
        self.assertNotIn("Phase 3", section)

    def test_last_phase_section_stops_before_the_trailing_sections(self):
        section = waves.wave_section_text(self.text, self.waves["W5"])
        self.assertIn("T009", section)
        self.assertNotIn("Dependencies & Execution Order", section)


class DocumentFrameTest(unittest.TestCase):
    """The conventions and policy a phase section leaves out."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = FIXTURE.read_text(encoding="utf-8")
        cls.waves = waves.parse_tasks(cls.text)
        cls.preamble, cls.policy = waves.document_frame(cls.text, cls.waves)

    def test_preamble_carries_the_conventions_above_the_first_phase(self):
        self.assertIn("## Format:", self.preamble)
        self.assertIn("## Path Conventions", self.preamble)

    def test_preamble_drops_the_yaml_frontmatter(self):
        self.assertFalse(self.preamble.startswith("---"))
        self.assertNotIn("description:", self.preamble)

    def test_preamble_stops_at_the_first_phase(self):
        self.assertNotIn("Phase 1: Setup", self.preamble)
        self.assertNotIn("T001", self.preamble)

    def test_policy_carries_the_sections_below_the_last_phase(self):
        self.assertIn("Dependencies & Execution Order", self.policy)
        self.assertIn("Implementation Strategy", self.policy)
        self.assertIn("## Notes", self.policy)

    def test_policy_starts_after_the_last_phase(self):
        self.assertNotIn("T009", self.policy)
        self.assertNotIn("Phase 5:", self.policy)

    def test_policy_keeps_fenced_content_verbatim(self):
        # A fenced heading is not a wave, and travelling as policy must not
        # turn it into one either.
        self.assertIn("Phase 99", self.policy)
        self.assertIn("Phase 98", self.policy)

    def test_a_document_with_no_phases_has_no_frame(self):
        self.assertEqual(waves.document_frame("# Tasks\n\nnothing here.\n", []), ("", ""))


class WaveCommandOutputTest(unittest.TestCase):
    """What an implementer or a verifier actually receives."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        feature = self.tmp / "specs" / "007-widget-catalogue"
        feature.mkdir(parents=True)
        shutil.copy(FIXTURE, feature / "tasks.md")
        specify = self.tmp / ".specify"
        specify.mkdir()
        (specify / "feature.json").write_text(
            json.dumps({"feature_directory": "specs/007-widget-catalogue"}),
            encoding="utf-8",
        )

    def run_cli(self, *args: str) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = waves.main(["--repo-root", str(self.tmp), *args])
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_wave_carries_the_assignment_between_the_two_frames(self):
        out = self.run_cli("wave", "W2")
        self.assertIn("above the first phase", out)
        self.assertIn("## Path Conventions", out)
        self.assertIn("W2 — your assignment", out)
        self.assertIn("T003", out)
        self.assertIn("below the last phase", out)
        self.assertIn("## Notes", out)

    def test_wave_still_withholds_the_other_phases(self):
        out = self.run_cli("wave", "W2")
        self.assertNotIn("T001", out)
        self.assertNotIn("T009", out)

    def test_slice_only_returns_the_section_alone(self):
        out = self.run_cli("wave", "W2", "--slice-only")
        self.assertIn("T003", out)
        self.assertNotIn("## Path Conventions", out)
        self.assertNotIn("## Notes", out)
        self.assertNotIn("your assignment", out)


class MarkDoneTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FIXTURE.read_text(encoding="utf-8")
        self.waves = {w.id: w for w in waves.parse_tasks(self.text)}

    def test_only_the_named_tasks_are_flipped(self):
        new_text, flipped = waves.mark_tasks_done(
            self.text, self.waves["W2"], ["T003", "T005"]
        )
        self.assertEqual(flipped, ["T003", "T005"])
        reparsed = {w.id: w for w in waves.parse_tasks(new_text)}
        by_id = {t.id: t for t in reparsed["W2"].tasks}
        self.assertTrue(by_id["T003"].done)
        self.assertFalse(by_id["T004"].done)
        self.assertTrue(by_id["T005"].done)

    def test_an_id_from_another_wave_is_refused(self):
        with self.assertRaises(waves.WavesError) as caught:
            waves.mark_tasks_done(self.text, self.waves["W2"], ["T006"])
        self.assertIn("T006", str(caught.exception))

    def test_an_unknown_id_is_refused(self):
        with self.assertRaises(waves.WavesError):
            waves.mark_tasks_done(self.text, self.waves["W2"], ["T404"])

    def test_marking_an_already_done_task_is_not_reported_as_flipped(self):
        new_text, flipped = waves.mark_tasks_done(
            self.text, self.waves["W1"], ["T001"]
        )
        self.assertEqual(flipped, [])
        self.assertEqual(new_text, self.text)

    def test_nothing_outside_the_task_line_is_touched(self):
        new_text, _ = waves.mark_tasks_done(self.text, self.waves["W2"], ["T003"])
        self.assertEqual(len(new_text.splitlines()), len(self.text.splitlines()))
        self.assertIn("- [ ] T900 This task line lives inside a fence", new_text)


class StateMachineTest(unittest.TestCase):
    """The state file is the script's own. Every layer talks to it here."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        feature = self.tmp / "specs" / "007-widget-catalogue"
        feature.mkdir(parents=True)
        shutil.copy(FIXTURE, feature / "tasks.md")
        specify = self.tmp / ".specify"
        specify.mkdir()
        (specify / "feature.json").write_text(
            json.dumps({"feature_directory": "specs/007-widget-catalogue"}),
            encoding="utf-8",
        )

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = waves.main(["--repo-root", str(self.tmp), *args])
        return code, out.getvalue(), err.getvalue()

    def state(self) -> dict:
        path = self.tmp / ".specify" / "waves" / "007-widget-catalogue.json"
        return json.loads(path.read_text(encoding="utf-8"))

    # -- L1 opens a wave ---------------------------------------------------

    def test_start_opens_the_wave_and_zeroes_the_rounds(self):
        code, out, _ = self.run_cli("start", "W2")
        self.assertEqual(code, 0)
        self.assertIn("W2", out)
        self.assertEqual(self.state()["waves"]["W2"]["rounds"], 0)

    def test_start_refuses_a_wave_that_is_already_finished(self):
        code, _, err = self.run_cli("start", "W1")
        self.assertEqual(code, 2)
        self.assertIn("already complete", err)

    def test_state_dir_gitignores_itself(self):
        self.run_cli("start", "W2")
        ignore = self.tmp / ".specify" / "waves" / ".gitignore"
        self.assertEqual(ignore.read_text(encoding="utf-8").strip(), "*")

    # -- L2 counts its own rounds -----------------------------------------

    def test_round_counts_up_from_one(self):
        self.run_cli("start", "W2")
        for expected in (1, 2, 3):
            code, out, _ = self.run_cli("round", "W2", "--max", "3")
            self.assertEqual(code, 0)
            self.assertIn(f"round {expected}/3", out)

    def test_round_past_the_ceiling_blocks_the_wave(self):
        self.run_cli("start", "W2")
        for _ in range(3):
            self.run_cli("round", "W2", "--max", "3")
        code, _, err = self.run_cli("round", "W2", "--max", "3")
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", err)
        self.assertIsNotNone(self.state()["waves"]["W2"]["blocked"])

    def test_a_blocked_wave_refuses_another_round_and_another_start(self):
        self.run_cli("start", "W2")
        self.run_cli("report", "W2", "--status", "blocked", "--reason", "spec conflict")
        self.assertEqual(self.run_cli("round", "W2")[0], 2)
        self.assertEqual(self.run_cli("start", "W2")[0], 2)

    def test_start_zeroes_rounds_from_a_previous_dispatch(self):
        self.run_cli("start", "W2")
        self.run_cli("round", "W2")
        self.run_cli("round", "W2")
        self.run_cli("start", "W2")
        self.assertEqual(self.state()["waves"]["W2"]["rounds"], 0)

    # -- L2 reports, L1 reads ---------------------------------------------

    def test_report_pass_is_read_back_with_the_round_count(self):
        self.run_cli("start", "W2")
        self.run_cli("round", "W2")
        self.run_cli("round", "W2")
        code, _, _ = self.run_cli(
            "report", "W2", "--status", "pass", "--tasks", "T003", "T004", "T005"
        )
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("result", "W2", "--json")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(result["tasks"], ["T003", "T004", "T005"])

    def test_report_refuses_a_task_from_another_wave(self):
        self.run_cli("start", "W2")
        code, _, err = self.run_cli(
            "report", "W2", "--status", "pass", "--tasks", "T006"
        )
        self.assertEqual(code, 2)
        self.assertIn("T006", err)

    def test_report_blocked_carries_the_reason_and_halts_the_run(self):
        self.run_cli("start", "W2")
        self.run_cli("round", "W2")
        self.run_cli(
            "report", "W2", "--status", "blocked", "--reason", "DECISION_REQUIRED: x"
        )
        code, out, _ = self.run_cli("result", "W2", "--json")
        result = json.loads(out)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("DECISION_REQUIRED", result["reason"])
        _, listing, _ = self.run_cli("list", "--json")
        self.assertTrue(json.loads(listing)["halted"])

    def test_result_before_any_report_is_a_refusal(self):
        self.run_cli("start", "W2")
        code, _, err = self.run_cli("result", "W2")
        self.assertEqual(code, 2)
        self.assertIn("no result", err.lower())

    def test_a_new_dispatch_supersedes_the_previous_result(self):
        self.run_cli("start", "W2")
        self.run_cli("report", "W2", "--status", "pass", "--tasks", "T003")
        self.run_cli("start", "W2")
        self.assertEqual(self.run_cli("result", "W2")[0], 2)

    # -- L1 commits the outcome -------------------------------------------

    def test_complete_ticks_the_tasks_the_result_named(self):
        self.run_cli("start", "W2")
        self.run_cli("report", "W2", "--status", "pass", "--tasks", "T003", "T004", "T005")
        code, out, _ = self.run_cli("complete", "W2", "T003", "T004", "T005")
        self.assertEqual(code, 0)
        self.assertIn("remaining: none", out)
        _, listing, _ = self.run_cli("list", "--json")
        parsed = {w["id"]: w for w in json.loads(listing)["waves"]}
        self.assertEqual(parsed["W2"]["status"], "PASS")
        self.assertEqual(json.loads(listing)["next"], "W3")

    def test_unblock_clears_the_halt_and_the_rounds(self):
        self.run_cli("start", "W2")
        self.run_cli("report", "W2", "--status", "blocked", "--reason", "x")
        code, _, _ = self.run_cli("unblock", "W2", "--reset-rounds")
        self.assertEqual(code, 0)
        self.assertEqual(self.run_cli("start", "W2")[0], 0)


if __name__ == "__main__":
    unittest.main()
