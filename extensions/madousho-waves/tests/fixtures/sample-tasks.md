---
description: "Synthetic fixture for the tasks.md parser. Not derived from any real project."
---

# Tasks: Widget Catalogue

**Input**: Design documents from `specs/007-widget-catalogue/`

## Format: `[ID] [P?] [Story] Description`

- `[P]` means the task touches files no sibling task touches.
- `[US#]` maps the task to a user story.

## Path Conventions

Paths below are relative to the repository root.

---

## Phase 1: Setup

**Purpose**: Bring the crate into existence so later phases have somewhere to write.

- [X] T001 Create the crate skeleton at `crates/widget-catalogue/`.
- [X] T002 [P] Record the dependency baseline in `specs/007-widget-catalogue/quickstart.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Types every story below depends on.

### The column types

- [ ] T003 Add the `WidgetId` column type. Test first: any other spelling is refused.
- [ ] T004 [P] Add the `WidgetName` column type with a 1..=64 length bound.

### The configuration

- [ ] T005 Parse the `[catalogue]` configuration section, rejecting an absent section.

---

## Phase 3: User Story 1 — Publish a widget (Priority: P1) 🎯 MVP

**Goal**: A widget written through the API can be read back.

- [ ] T006 [US1] Add the `POST /widgets` route.
- [ ] T007 [P] [US1] Add the `GET /widgets` route.

---

## Phase 4: User Story 2 — Withdraw a widget (Priority: P2)

- [ ] T008 [US2] Add the `DELETE /widgets/{id}` route.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T009 Regenerate the API document and re-run the whole suite.

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 2 blocks every phase after it.
- Phase 3 and Phase 4 are independent of one another.
- [ ] T902 A task-shaped line outside every phase must not be collected.

## Parallel Example: Phase 2

```bash
# The column types and the configuration parser are different modules.
## Phase 99: This heading lives inside a fence and must be ignored
- [ ] T900 This task line lives inside a fence and must be ignored
Task: "T003 WidgetId in src/models/widget.rs"
Task: "T005 catalogue config in src/config.rs"
```

~~~text
## Phase 98: A tilde fence must be honoured too
- [ ] T901 Another line that must not be counted
~~~

## Implementation Strategy

Deliver Phase 1 through Phase 3 first; that is the MVP.

## Notes

- T003 is the only task that blocks both stories, so it is worth doing first.
- A task marked `- [ ]` in this prose sentence is not a task line because it carries no ID.
