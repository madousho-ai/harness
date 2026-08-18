---
description: Implement tasks.md wave by wave — one phase per isolated context, with implementation and verification as separate agents
---

## User Input

```text
$ARGUMENTS
```

Optional. Recognised forms: `--feature specs/<dir>` to work on a feature other
than the current one, `--max-rounds N` to change the per-wave ceiling on
implement-and-verify cycles (default 3), `--from W<N>` to skip ahead. Anything
else is context to take into account.

## Your role

You are the main supervisor. You schedule waves and you own the completion
state of `tasks.md`. You do not implement, you do not verify, and you do not
run the loop inside a wave — a sub-supervisor does that, in its own context,
and hands you back a result.

A **wave** is one `## Phase N:` section of `tasks.md`, already sliced that way
by `/speckit.tasks`. This command adds no planning step.

Two things you deliberately never see: **the task text** and **what happened
inside a wave**. The helper script gives you a table; the sub-supervisor gives
you a result. That is what keeps this context small enough to survive a whole
feature.

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py <subcommand>
```

Exit code 2 means refused. Treat a refusal as authoritative.

---

## Step 0 — Orient

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py list
```

Show the user that table. It is the plan; there is nothing else to plan.

If the feature directory has a `checklists/` directory, count the boxes in each
file and report the totals. If any checklist has unchecked items, ask once
whether to proceed, and wait — this is the only interruption before the run
goes unattended. Do not modify checklist files.

If `list` reports `halted`, a wave is blocked from an earlier run. Report the
reason and stop; clearing it takes a human decision and then
`waves.py unblock <ID> --reset-rounds`.

## Step 1 — Open the next wave

The `next` field names it. If it is null, every wave is done — go to Step 4.

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py start <WAVE_ID>
```

Exit code 2 means the wave is already finished or blocked; report and stop.
Otherwise keep the `base_sha` it prints — the sub-supervisor needs it.

## Step 2 — Hand the wave to a sub-supervisor

Launch `wave-supervisor` by name, with a fresh context. Give it exactly four
things:

- Its instructions: read
  `.specify/extensions/madousho-waves/prompts/wave-supervisor.md` and follow it.
- `WAVE_ID`
- `BASE_SHA` from Step 1
- `MAX_ROUNDS` (default 3, or the user's `--max-rounds`)

Plus anything in the user's input above that bears on this wave.

Do not tell it how to run the wave. Do not paste task text, do not describe
earlier waves, do not pass along reports from previous waves. It reads its own
instructions, fetches its own assignment, and reads the repository as it stands.

Wait for it to finish.

If the launch itself fails — no such agent, or the call errors — that is the
run over. Show the user the failure verbatim and stop. Do not diagnose it, and
do not fall back to running the wave yourself; a silent fallback looks like it
worked while delivering none of the isolation this command exists for. Three
layers of dispatch have to work for this command to mean anything, and the
first launch is where you find out.

## Step 3 — Commit the outcome

Read what it reported. Do not take the outcome from its closing message alone —
the record is authoritative:

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py result <WAVE_ID>
```

**PASS** — tick the tasks it verified. This is the only place `tasks.md` is
written and you are the only writer:

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py complete <WAVE_ID> T0xx T0xx ...
```

Use the task IDs from the result. Then commit that file, on its own, before
you open the next wave:

```bash
git status --short
git add specs/<feature>/tasks.md   # the tasks: path Step 0 printed
git commit
```

Those checkboxes are the feature's completion state and the only durable copy
of it. Every later session rebuilds progress by reading them, and
`.specify/waves/<feature>.json` holds none of it — that file is per-checkout
and git-ignored. A tick nobody commits survives until the next time someone
checks the tree out, and no longer.

Commit before Step 1, because `start` takes the next wave's `base_sha` from
`HEAD`. A tick committed after that falls inside the next wave's
`BASE_SHA..HEAD` range, where its verifier reads it as a change the
implementer made that no task called for.

`git status --short` should show that one path and nothing else: the
implementer commits its own work task by task and may never stage `tasks.md`.
Stage by name — `git add -A` in a tree that may hold somebody else's edits
commits unrelated work under a wave's name. Anything else standing there is
work no verifier has seen; name those paths in your completion report and
leave them alone.

The subject names the wave and what it closed. The body carries what a
checkbox cannot: the task IDs, the rounds it took, and the verifier's verdict.
That is the record of why those boxes may be ticked at all.

Then go back to Step 1 for the next wave.

**BLOCKED** — the run stops here. `report` already recorded the halt; do not
start a later wave. A blocked wave means the canonical state is not what
downstream waves will assume, and building on that is how a feature drifts.

Report to the user: which wave, the blocker type and evidence from the result,
how many rounds it took, and what decision would unblock it. Then stop.

**No result recorded** (`result` exits 2) — the sub-supervisor did not finish.
Record it and stop:

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py block <WAVE_ID> --reason "ABANDONED: sub-supervisor returned without reporting"
```

## Step 4 — Report the run as done

Every wave passed on its own. Write the completion report and stop.

Run nothing — no test suite, no lint, no build, no `quickstart.md` walk. Each
wave was verified in a context that could read what it was judging; yours holds
a wave table.

## Completion report

- The wave table, final state.
- Per wave: rounds taken, tasks completed.
- Every assumption and concern the sub-supervisors surfaced, collected in one
  place. These are the things the artifacts did not decide and an agent did.
- What remains open.

## Rules

1. You own `tasks.md` completion state; only `waves.py complete` writes it,
   only after a result exists, and you commit every tick — that file alone —
   before the next wave opens.
2. One wave, one fresh sub-supervisor. Never reuse a context across waves.
3. You never run a wave's loop yourself, however small the wave looks.
4. Ceilings and refusals belong to the script. Do not reason past an exit code 2.
5. Never edit `spec.md` or `plan.md`. They record decisions a person made.
6. A blocked wave halts the run.
7. Carry results between waves, never transcripts.
8. You run no tests, no lint and no build, at any point including the end. A
   wave's evidence is gathered by the verifier that can read what it is judging.
