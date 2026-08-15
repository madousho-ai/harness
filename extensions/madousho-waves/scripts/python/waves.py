#!/usr/bin/env python3
"""Read a Spec Kit ``tasks.md`` as a list of Waves, and hold the run state.

A Wave is one ``## Phase N: ...`` section of ``tasks.md``. The phases are
already produced by ``/speckit.tasks``; nothing here plans or re-slices them.

The point of this script is that no agent ever has to read the whole
``tasks.md``. The supervisor reads ``list`` (one line per Wave); the
implementer reads ``wave <id>`` (one phase, verbatim). Completion state lives
in the checkboxes of ``tasks.md`` itself, so a fresh session rebuilds progress
from the file rather than from anybody's memory.

Two things ``tasks.md`` cannot hold live in ``.specify/waves/<feature>.json``:
how far a wave got, and the commit it started from. Nobody hand-writes that
file — every layer reaches it through a subcommand here, so the retry ceiling
is counted rather than promised:

===========================  =====  ==========================================
subcommand                   layer  purpose
===========================  =====  ==========================================
``list``                     L1     the wave table, what is next, whether halted
``start <id>``               L1     open a wave: record its starting commit
``round <id>``               L2     one implement+verify cycle; refuses past the ceiling
``wave <id>``                L3     that wave's slice of tasks.md, verbatim
``report <id> --status ...`` L2     the wave result L1 acts on
``result <id>``              L1     read that result back
``complete <id> T...``       L1     tick the checkboxes — the only writer of tasks.md
``block`` / ``unblock``      L1     halt, and clear the halt after a human decides
===========================  =====  ==========================================

Exit codes: 0 ok, 1 usage or environment error, 2 refused.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = 2
DEFAULT_MAX_ROUNDS = 3

# Only ``## Phase N: title`` opens a Wave. Every other H2 closes the open one,
# which is what keeps the trailing sections of tasks.md (Dependencies,
# Requirement Coverage, Notes) from collecting task-shaped lines.
PHASE_HEADING_RE = re.compile(r"^##\s+Phase\s+(\d+)\s*[:：]\s*(.+?)\s*$")
ANY_H2_RE = re.compile(r"^##\s+\S")
TASK_RE = re.compile(r"^- \[([ xX])\]\s+(T\d+)\b(.*)$")
# A fenced block may carry lines that look exactly like headings or tasks;
# tasks.md routinely does, in its parallel-execution examples.
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
STORY_RE = re.compile(r"\[US(\d+)\]")
HEADING_STORY_RE = re.compile(r"\bUser Story\s+(\d+)\b")
PARALLEL_RE = re.compile(r"^\s*\[P\]")

STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL"
STATUS_PENDING = "PENDING"
STATUS_BLOCKED = "BLOCKED"


class WavesError(Exception):
    """Refused: the request was understood and is not allowed."""


@dataclass
class Task:
    id: str
    done: bool
    parallel: bool
    stories: list[str]
    line_no: int  # 1-based, into the file the wave was parsed from
    text: str


@dataclass
class Wave:
    id: str
    phase: int
    title: str
    heading: str
    start_line: int  # 1-based, the heading line
    end_line: int  # 1-based, last line owned by this wave
    tasks: list[Task] = field(default_factory=list)
    stories: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def done(self) -> int:
        return sum(1 for task in self.tasks if task.done)

    @property
    def remaining(self) -> list[str]:
        return [task.id for task in self.tasks if not task.done]

    @property
    def status(self) -> str:
        if self.total and self.done == self.total:
            return STATUS_PASS
        if self.done:
            return STATUS_PARTIAL
        return STATUS_PENDING

    @property
    def span(self) -> str:
        if not self.tasks:
            return "—"
        if len(self.tasks) == 1:
            return self.tasks[0].id
        return f"{self.tasks[0].id}–{self.tasks[-1].id}"


# -- parsing ----------------------------------------------------------------


def _dedupe(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def parse_tasks(text: str) -> list[Wave]:
    """Return one Wave per ``## Phase N:`` heading, in document order."""
    lines = text.splitlines()
    result: list[Wave] = []
    current: Wave | None = None
    fence: tuple[str, int] | None = None

    for index, line in enumerate(lines, start=1):
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            char, length = marker[0], len(marker)
            if fence is None:
                fence = (char, length)
                continue
            if char == fence[0] and length >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue

        heading = PHASE_HEADING_RE.match(line)
        if heading:
            if current is not None:
                current.end_line = index - 1
                result.append(current)
            phase = int(heading.group(1))
            title = heading.group(2).strip()
            current = Wave(
                id=f"W{len(result) + 1}",
                phase=phase,
                title=title,
                heading=line.rstrip(),
                start_line=index,
                end_line=index,
            )
            story = HEADING_STORY_RE.search(title)
            if story:
                current.stories.append(f"US{story.group(1)}")
            continue

        if ANY_H2_RE.match(line):
            if current is not None:
                current.end_line = index - 1
                result.append(current)
                current = None
            continue

        task = TASK_RE.match(line)
        if task and current is not None:
            remainder = task.group(3)
            current.tasks.append(
                Task(
                    id=task.group(2),
                    done=task.group(1) in ("x", "X"),
                    parallel=bool(PARALLEL_RE.match(remainder)),
                    stories=[f"US{n}" for n in STORY_RE.findall(remainder)],
                    line_no=index,
                    text=line.rstrip(),
                )
            )

    if current is not None:
        current.end_line = len(lines)
        result.append(current)

    for wave in result:
        wave.stories = _dedupe(
            wave.stories + [story for task in wave.tasks for story in task.stories]
        )
    return result


def next_wave(waves: list[Wave]) -> Wave | None:
    """The first Wave that is not finished, or None when every Wave is done."""
    for wave in waves:
        if wave.status != STATUS_PASS:
            return wave
    return None


def find_wave(waves: list[Wave], wave_id: str) -> Wave:
    wanted = wave_id.upper()
    for wave in waves:
        if wave.id == wanted:
            return wave
    known = ", ".join(wave.id for wave in waves) or "none"
    raise WavesError(f"No wave {wave_id!r}. Known waves: {known}.")


def wave_section_text(text: str, wave: Wave) -> str:
    """The Wave's own slice of tasks.md, verbatim."""
    lines = text.splitlines()
    return "\n".join(lines[wave.start_line - 1 : wave.end_line]).rstrip() + "\n"


def document_frame(text: str, waves: list[Wave]) -> tuple[str, str]:
    """The parts of ``tasks.md`` that belong to no single phase.

    A phase section carries its own tasks and the reason for each. What sits
    above the first phase and below the last one is a different kind of thing:
    conventions and policy that say how any task is to be carried out — path
    prefixes the task lines abbreviate, which tasks are exempt from the
    red-green rule, what a `[P]` does not promise, the scope fence. An agent
    handed only its own slice would follow the task text and still get these
    wrong, so both ends travel with every slice.

    Returns ``(preamble, policy)``, either of which may be empty. Any
    non-phase section sitting *between* two phases belongs to neither and is
    left out of both.
    """
    if not waves:
        return "", ""
    lines = text.splitlines()

    head = lines[: waves[0].start_line - 1]
    if head[:1] == ["---"]:
        closing = next(
            (i for i in range(1, len(head)) if head[i].strip() == "---"), None
        )
        if closing is not None:
            head = head[closing + 1 :]

    return "\n".join(head).strip(), "\n".join(lines[waves[-1].end_line :]).strip()


def _banner(caption: str) -> str:
    return f"===== {caption} ====="


def check_membership(wave: Wave, task_ids: list[str]) -> None:
    """Refuse task IDs that belong to another wave.

    A wave may only speak for its own tasks — whether it is ticking them or
    reporting them as verified.
    """
    known = {task.id for task in wave.tasks}
    stray = [task_id for task_id in task_ids if task_id not in known]
    if stray:
        raise WavesError(
            f"{', '.join(stray)} not in {wave.id} "
            f"({wave.span}). A wave may only speak for its own tasks."
        )


def mark_tasks_done(
    text: str, wave: Wave, task_ids: list[str]
) -> tuple[str, list[str]]:
    """Tick the given tasks in *wave*. Returns the new text and what changed."""
    check_membership(wave, task_ids)
    by_id = {task.id: task for task in wave.tasks}

    lines = text.splitlines()
    flipped: list[str] = []
    for task_id in task_ids:
        task = by_id[task_id]
        if task.done:
            continue
        index = task.line_no - 1
        lines[index] = lines[index].replace("- [ ]", "- [X]", 1)
        flipped.append(task_id)

    if not flipped:
        return text, []
    new_text = "\n".join(lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, flipped


# -- project layout ---------------------------------------------------------


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".specify").is_dir():
            return candidate
    raise WavesError(
        f"No .specify/ directory at or above {start}. "
        f"Run this from inside a Spec Kit project."
    )


def find_feature_dir(repo_root: Path, override: str | None) -> Path:
    if override:
        path = (repo_root / override).resolve() if not Path(override).is_absolute() else Path(override)
        if not path.is_dir():
            raise WavesError(f"No such feature directory: {path}")
        return path
    pointer = repo_root / ".specify" / "feature.json"
    if not pointer.is_file():
        raise WavesError(
            "No .specify/feature.json — pass --feature specs/<dir> to say "
            "which feature to work on."
        )
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WavesError(f"Could not read {pointer}: {exc}") from exc
    directory = data.get("feature_directory")
    if not directory:
        raise WavesError(f"{pointer} has no 'feature_directory' key.")
    path = repo_root / directory
    if not path.is_dir():
        raise WavesError(f"{pointer} points at {path}, which does not exist.")
    return path


def tasks_path(feature_dir: Path) -> Path:
    path = feature_dir / "tasks.md"
    if not path.is_file():
        raise WavesError(f"No tasks.md in {feature_dir}. Run /speckit.tasks first.")
    return path


# -- run state --------------------------------------------------------------


class RunState:
    """What tasks.md cannot hold: rounds taken, starting commit, wave result."""

    def __init__(self, path: Path, feature: str):
        self.path = path
        self.feature = feature
        self.data: dict = {"schema": SCHEMA, "feature": feature, "waves": {}}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict) and loaded.get("schema") == SCHEMA:
                self.data = loaded
                self.data.setdefault("waves", {})

    def wave(self, wave_id: str) -> dict:
        return self.data["waves"].setdefault(
            wave_id, {"base_sha": None, "rounds": 0, "reported": None, "blocked": None}
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # The directory holds per-checkout run state; keep it out of git
        # without editing a .gitignore this script does not own.
        ignore = self.path.parent / ".gitignore"
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def head_sha(repo_root: Path) -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


# -- commands ---------------------------------------------------------------


@dataclass
class Context:
    repo_root: Path
    feature_dir: Path
    tasks_file: Path
    text: str
    waves: list[Wave]
    state: RunState


def load(args: argparse.Namespace) -> Context:
    repo_root = find_repo_root(Path(args.repo_root).resolve() if args.repo_root else Path.cwd())
    feature_dir = find_feature_dir(repo_root, args.feature)
    tasks_file = tasks_path(feature_dir)
    text = tasks_file.read_text(encoding="utf-8")
    state_path = repo_root / ".specify" / "waves" / f"{feature_dir.name}.json"
    return Context(
        repo_root=repo_root,
        feature_dir=feature_dir,
        tasks_file=tasks_file,
        text=text,
        waves=parse_tasks(text),
        state=RunState(state_path, feature_dir.name),
    )


def wave_status(wave: Wave, record: dict) -> str:
    if record.get("blocked") and wave.status != STATUS_PASS:
        return STATUS_BLOCKED
    return wave.status


def cmd_list(context: Context, args: argparse.Namespace) -> int:
    rows = []
    for wave in context.waves:
        record = context.state.wave(wave.id)
        reported = record.get("reported") or {}
        rows.append(
            {
                "id": wave.id,
                "phase": wave.phase,
                "title": wave.title,
                "span": wave.span,
                "tasks": [task.id for task in wave.tasks],
                "total": wave.total,
                "done": wave.done,
                "stories": wave.stories,
                "status": wave_status(wave, record),
                "rounds": record.get("rounds", 0),
                "base_sha": record.get("base_sha"),
                "reported": reported.get("status"),
                "blocked": record.get("blocked"),
            }
        )
    upcoming = next((row for row in rows if row["status"] != STATUS_PASS), None)
    payload = {
        "feature": context.feature_dir.name,
        "tasks_file": str(context.tasks_file.relative_to(context.repo_root)),
        "waves": rows,
        "next": upcoming["id"] if upcoming else None,
        "halted": bool(upcoming and upcoming["status"] == STATUS_BLOCKED),
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"feature: {payload['feature']}   tasks: {payload['tasks_file']}")
    for row in rows:
        story = f" [{'+'.join(row['stories'])}]" if row["stories"] else ""
        rounds = f"  {row['rounds']} round(s)" if row["rounds"] else ""
        print(
            f"  {row['id']:<4} {row['status']:<8} {row['done']:>2}/{row['total']:<3} "
            f"{row['span']:<12} {row['title']}{story}{rounds}"
        )
        if row["blocked"]:
            print(f"       blocked: {row['blocked']}")
    if payload["halted"]:
        print(f"\nhalted at {payload['next']} — see the blocked reason above")
    elif payload["next"]:
        print(f"\nnext: {payload['next']}")
    else:
        print("\nevery wave is complete")
    return 0


def cmd_wave(context: Context, args: argparse.Namespace) -> int:
    wave = find_wave(context.waves, args.wave)
    section = wave_section_text(context.text, wave)
    if args.slice_only:
        sys.stdout.write(section)
        return 0

    preamble, policy = document_frame(context.text, context.waves)
    parts: list[str] = []
    if preamble:
        parts.append(_banner("tasks.md, above the first phase — applies to every wave"))
        parts.append(preamble)
    parts.append(_banner(f"{wave.id} — your assignment"))
    parts.append(section.rstrip())
    if policy:
        parts.append(_banner("tasks.md, below the last phase — applies to every wave"))
        parts.append(policy)
    sys.stdout.write("\n\n".join(parts) + "\n")
    return 0


def cmd_start(context: Context, args: argparse.Namespace) -> int:
    """L1 opens a wave. One dispatch; the rounds inside it belong to L2."""
    wave = find_wave(context.waves, args.wave)
    record = context.state.wave(wave.id)

    if wave.status == STATUS_PASS:
        print(f"{wave.id} is already complete ({wave.done}/{wave.total}).", file=sys.stderr)
        return 2
    if record.get("blocked"):
        print(f"{wave.id} is blocked: {record['blocked']}", file=sys.stderr)
        return 2

    if record.get("base_sha") is None:
        # Recorded once per wave, never per round: the verifier must see the
        # whole wave including its repairs.
        record["base_sha"] = head_sha(context.repo_root)
    record["rounds"] = 0
    # A fresh dispatch supersedes whatever the previous one concluded.
    record["reported"] = None
    context.state.save()

    payload = {
        "wave": wave.id,
        "base_sha": record["base_sha"],
        "remaining": wave.remaining,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"{wave.id} open — {len(wave.remaining)} task(s) to do")
        print(f"base_sha: {record['base_sha'] or '(not a git repository)'}")
        print(f"remaining: {' '.join(wave.remaining) or 'none'}")
    return 0


def cmd_round(context: Context, args: argparse.Namespace) -> int:
    """L2 opens one implement+verify cycle. The ceiling is enforced here."""
    wave = find_wave(context.waves, args.wave)
    record = context.state.wave(wave.id)

    if record.get("blocked"):
        print(f"{wave.id} is blocked: {record['blocked']}", file=sys.stderr)
        return 2

    number = record.get("rounds", 0) + 1
    if number > args.max:
        record["blocked"] = (
            f"RETRY_LIMIT_EXCEEDED: {args.max} round(s) of implement and verify "
            f"with {len(wave.remaining)} task(s) still open"
        )
        context.state.save()
        print(f"{wave.id} BLOCKED: {record['blocked']}", file=sys.stderr)
        return 2

    record["rounds"] = number
    context.state.save()
    print(f"{wave.id} round {number}/{args.max}")
    return 0


def cmd_report(context: Context, args: argparse.Namespace) -> int:
    """L2 states how the wave ended. L1 acts on this and nothing else."""
    wave = find_wave(context.waves, args.wave)
    record = context.state.wave(wave.id)
    status = args.status.upper()

    tasks = args.tasks or []
    check_membership(wave, tasks)

    if status == STATUS_BLOCKED and not args.reason:
        raise WavesError("A blocked wave must say why: pass --reason.")

    record["reported"] = {
        "status": status,
        "tasks": tasks,
        "reason": args.reason,
        "rounds": record.get("rounds", 0),
    }
    if status == STATUS_BLOCKED:
        record["blocked"] = args.reason
    context.state.save()

    print(f"{wave.id} reported {status} after {record['rounds']} round(s)")
    if tasks:
        print(f"verified: {' '.join(tasks)}")
    return 0


def cmd_result(context: Context, args: argparse.Namespace) -> int:
    """L1 reads what L2 reported. This is the whole of the handoff."""
    wave = find_wave(context.waves, args.wave)
    reported = context.state.wave(wave.id).get("reported")
    if not reported:
        print(f"error: no result reported for {wave.id}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"wave": wave.id, **reported}, indent=2, ensure_ascii=False))
        return 0
    print(f"wave:   {wave.id}")
    print(f"status: {reported['status']}")
    print(f"rounds: {reported['rounds']}")
    print(f"tasks:  {' '.join(reported['tasks']) or 'none'}")
    if reported.get("reason"):
        print(f"reason: {reported['reason']}")
    return 0


def cmd_complete(context: Context, args: argparse.Namespace) -> int:
    wave = find_wave(context.waves, args.wave)
    new_text, flipped = mark_tasks_done(context.text, wave, args.tasks)
    if flipped:
        temporary = context.tasks_file.with_suffix(".md.tmp")
        temporary.write_text(new_text, encoding="utf-8")
        temporary.replace(context.tasks_file)
    still_open = [task_id for task_id in wave.remaining if task_id not in flipped]
    print(f"{wave.id}: ticked {' '.join(flipped) or 'nothing'}")
    print(f"remaining: {' '.join(still_open) or 'none'}")
    return 0


def cmd_block(context: Context, args: argparse.Namespace) -> int:
    wave = find_wave(context.waves, args.wave)
    record = context.state.wave(wave.id)
    record["blocked"] = args.reason
    context.state.save()
    print(f"{wave.id} BLOCKED: {args.reason}", file=sys.stderr)
    return 2


def cmd_unblock(context: Context, args: argparse.Namespace) -> int:
    wave = find_wave(context.waves, args.wave)
    record = context.state.wave(wave.id)
    record["blocked"] = None
    if args.reset_rounds:
        record["rounds"] = 0
    context.state.save()
    print(f"{wave.id} cleared")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="waves.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo-root", help="Project root (default: search upwards from cwd)")
    parser.add_argument("--feature", help="Feature directory (default: .specify/feature.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="[L1] One line per wave, plus which is next")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(handler=cmd_list)

    status = sub.add_parser("status", help="Alias of list")
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=cmd_list)

    section = sub.add_parser(
        "wave", help="[L3] One wave's slice of tasks.md, with the document's own policy"
    )
    section.add_argument("wave")
    section.add_argument(
        "--slice-only",
        action="store_true",
        help="The phase section alone, without the conventions and policy around it",
    )
    section.set_defaults(handler=cmd_wave)

    start = sub.add_parser("start", help="[L1] Open a wave and record its starting commit")
    start.add_argument("wave")
    start.add_argument("--json", action="store_true")
    start.set_defaults(handler=cmd_start)

    rounds = sub.add_parser("round", help="[L2] Open one implement+verify cycle")
    rounds.add_argument("wave")
    rounds.add_argument("--max", type=int, default=DEFAULT_MAX_ROUNDS)
    rounds.set_defaults(handler=cmd_round)

    report = sub.add_parser("report", help="[L2] State how the wave ended")
    report.add_argument("wave")
    report.add_argument("--status", required=True, choices=["pass", "PASS", "blocked", "BLOCKED"])
    report.add_argument("--tasks", nargs="*", default=[], help="Task IDs the verifier confirmed")
    report.add_argument("--reason", help="Required when the status is blocked")
    report.set_defaults(handler=cmd_report)

    result = sub.add_parser("result", help="[L1] Read the wave result back")
    result.add_argument("wave")
    result.add_argument("--json", action="store_true")
    result.set_defaults(handler=cmd_result)

    complete = sub.add_parser("complete", help="[L1] Tick tasks — the only writer of tasks.md")
    complete.add_argument("wave")
    complete.add_argument("tasks", nargs="+")
    complete.set_defaults(handler=cmd_complete)

    block = sub.add_parser("block", help="[L1] Halt the run at this wave")
    block.add_argument("wave")
    block.add_argument("--reason", required=True)
    block.set_defaults(handler=cmd_block)

    unblock = sub.add_parser("unblock", help="[L1] Clear a halt after a human decision")
    unblock.add_argument("wave")
    unblock.add_argument("--reset-rounds", action="store_true")
    unblock.set_defaults(handler=cmd_unblock)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        context = load(args)
        return args.handler(context, args)
    except WavesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
