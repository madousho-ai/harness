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

## Prerequisite — nested sub-agents

This command needs an agent that can launch sub-agents **two levels deep**: you
launch a sub-supervisor, and it launches an implementer and a verifier.

Checking this is your job and yours alone. The sub-supervisor assumes the
capability and will not test for it, so anything you miss here surfaces as a
wave that halts after doing no work.

**Establish it by doing it.** Launch the probe below and see whether `PONG`
comes back. That single call settles the question, and nothing you can read
settles it.

### The probe

Launch `wave-supervisor` by name, giving it this and nothing else:

> CAPABILITY PROBE. There is no wave. Do not read any protocol file, do not run
> `waves.py`, do not write anything, do not read the repository. Do exactly one
> thing: launch a `wave-implement` sub-agent whose entire instruction is to
> reply with the single word `PONG`. Report back either the word it returned,
> or — if the launch itself failed — the verbatim failure. Do not list your
> tools, do not describe them, do not diagnose anything, do not state which
> layer you think you are.

`PONG` means both gates are open; go to Step 0. It costs no wave round, because
nothing has been started yet.

Anything else means stop. Report to the user verbatim what came back, then the
two candidate causes below.

### The two things that shut a gate

Both wear the same face — the sub-supervisor comes up with no launcher at all —
and neither is visible in a config that reads as correct.

**Depth.** `subagent_depth` absent or `1`. It goes in `opencode.json` (project)
or `~/.config/opencode/opencode.jsonc` (global), and needs a restart:

```json
{ "subagent_depth": 2 }
```

**The `task` grant.** A subagent receives the `task` tool only if its own
definition holds an entry whose key is literally `task`; a wildcard
`"*": "allow"` does not satisfy that, and the built-in `general` has no such
entry. When `task` is given the object form, rules are evaluated in declaration
order and **the last match wins**, so

```jsonc
"task": { "wave-implement": "allow", "wave-verify": "allow", "*": "deny" }
```

denies both agents it appears to permit — each matches its own rule, then
matches `*`, and `*` is last. A denied subagent is dropped from the `task` tool
description outright, so denying every candidate removes the tool itself. The
catch-all goes first:

```jsonc
"task": { "*": "deny", "wave-implement": "allow", "wave-verify": "allow" }
```

Raise these **after** a probe has failed. Reading them first proves nothing:
the second one reads as a correct, carefully narrowed permission right up until
someone notices the order.

### Tool names are not evidence

The names your tools arrive under are not a fact about opencode. A proxy or
gateway may rewrite every one of them in transit — `task` can reach you as
`mcp__<word>__<word>_task` — and the rewriting can differ from session to
session. Permission resolution happens on opencode's side of it and is
unaffected.

So do not conclude anything from the shape of a tool name, do not ask any layer
below you to list its tools, and do not accept a name-shaped explanation in a
blocker report. A renamed tool has never been the cause of a failed dispatch
here. It has twice been the misdiagnosis, both times in a session where the
real cause was the rule order above.

If a gate is shut, stop and say so. Do not fall back to running the waves
yourself — a silent fallback looks like it worked while delivering none of the
isolation this command exists for.

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

Launch the agent you identified in Gate 2, by name, with a fresh context. Give
it exactly four things:

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

Use the task IDs from the result. Then go back to Step 1 for the next wave.

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

## Step 4 — Global verification

Reaching here means every wave passed on its own. Cross-wave problems are
invisible at those boundaries, so check the feature as a whole:

1. Run the project's full test suite, not just the parts a wave touched.
2. Run lint and build in the configurations `plan.md` names — feature flags,
   alternate backends, release profile.
3. Walk `spec.md` requirement by requirement and say where each is satisfied
   now. Anything you cannot point at is a finding.
4. Run `quickstart.md` end to end if it exists.
5. Confirm the git history reads as intended work: one task per commit, nothing
   committed that no task called for.

A failure here is a finding for the user, not something to fix silently.

## Completion report

- The wave table, final state.
- Per wave: rounds taken, tasks completed.
- Every assumption and concern the sub-supervisors surfaced, collected in one
  place. These are the things the artifacts did not decide and an agent did.
- Global verification results.
- What remains open.

## Rules

1. You own `tasks.md` completion state; only `waves.py complete` writes it, and
   only after a result exists.
2. One wave, one fresh sub-supervisor. Never reuse a context across waves.
3. You never run a wave's loop yourself, however small the wave looks.
4. Ceilings and refusals belong to the script. Do not reason past an exit code 2.
5. Never edit `spec.md` or `plan.md`. They record decisions a person made.
6. A blocked wave halts the run.
7. Carry results between waves, never transcripts.
