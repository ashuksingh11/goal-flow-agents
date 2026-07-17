# AGENTS.md — goal-flow-agents (coding-session guide)

Context for an AI/coding session. This is the **docs-only / cross-cutting** repo for
GoalFlow — a two-tier, goal-based agent POC for the Samsung Tizen Family Hub. It holds
no runnable code; the four code repos are siblings under `~/ashu/git/`.

## The system in one paragraph

A **cloud agent** (LangGraph/Python, owns conversation + memory + human-in-the-loop)
and an **on-device agent** (.NET 8 + Semantic Kernel, sole authority on local state +
actuators) collaborate over a WebSocket **hub** (the cloud) to fulfil a fuzzy,
long-running goal — e.g. *"help my family eat healthier this week and reduce food
waste"* → an adaptive, approval-gated weekly dinner plan. A **React tablet UI** is the
human surface. UI and device never talk directly. Two gates: a deterministic **safety
gate** (device code, blocks) and an **approval gate** (the user via the cloud, waits).
Slogan: *"LLM plans, code checks."* The POC proves the orchestration pattern; the
world is faked, the mechanism is real.

## The repos (all under ~/ashu/git/)

- `goal-flow-cloud-agent` — Python/FastAPI/LangGraph hub. **Owns canonical `CONTRACT.md`.**
- `goal-flow-device-agent-ubuntu` — .NET 8/SK device brain. **Current source of truth** for the device.
- `goal-flow-agent-chat-ui` — React/Vite/TS tablet UI.
- `goal-flow-device-agent-tizen` — Tizen port. **FROZEN pre-v2** (see its AGENTS.md).
- `goal-flow-agents` — this repo (docs).

Each code repo has its own `AGENTS.md` with run commands, key files, and gotchas —
read the relevant one before coding there.

## Docs in this repo (current vs historical)

- **Current:** `docs/V2_DESIGN_PROPOSAL.md` (the v2 architecture), `docs/FINAL_DEMO.md`
  (presenter script), `docs/UX_CONFIRM_UNDERSTANDING.md` and `docs/UX_EVENT_REDESIGN.md`
  (the two most recent UX design specs — the confirm-understanding gate and the
  event-driven meal week; these are the best source of truth for what changed).
- **Historical (v1, superseded):** `docs/SYSTEM_OVERVIEW.md`, `docs/DEMO_RUNBOOK.md`
  — kept for reference; they describe the retired v1 clock-advance / rules-planner
  design. Banner-flagged in-file.
- **Archival brainstorm:** `GoalFlow-discussions/{claude,gpt}/*.md` — design input, not
  frozen spec.
- `docs/README.md` indexes all of the above.

## Two features that post-date the original v2 docs (know these)

1. **Confirm-understanding gate** — before planning, the cloud shows its read
   (objective / constraints / thought / summary); the user Confirms (or Declines).
   Wire: `understanding` → `understanding_response`; cloud node `present_understanding`.
2. **Event-driven meal week** — the meal demo replaced "Advance day" with a strip of
   ~6 presenter-fired **event chips** (`EventStrip`). Firing a chip →
   `control trigger_event {event_id}` → one scoped-LLM adaptation → the plan card
   morphs the changed day row. Catalog seeded in the device's `data/daily_events.json`.

## Conventions

- **Branching (v3 onward):** a long-lived **`v3` integration branch** per repo; each
  milestone gets its own branch off `v3` — `v3-m2-task-manager`, … — merged back into
  `v3` with `--no-ff` when that milestone's gate passes, then deleted. `v3` → `master`
  **once**, when v3 ships (M9).

  ```
  master ──────────────────────────────────────────────►  last coherent v2
     └── v3 ──(M0)──(M1)──(M2)──…──(M9)──┐                 (all four surfaces work)
           └ v3-m2-task-manager ┘        └──► merge to master when v3 ships
  ```

  **Why master must NOT carry mid-v3 state:** v3 breaks things *on purpose* between
  milestones. M0 deletes `Modules/`, which the Tizen ports' copy recipe names
  (`for d in Agent Contracts Modules Transport; do diff -rq …; done`) — so from M0 until
  the M9 re-sync, any branch carrying v3 cannot satisfy that check. That intermediate
  state belongs on `v3`, not on the branch you'd fall back to for a demo. Same for the
  contract mirrors mid-M6. (This was learned the hard way: M0 and M1 were merged
  straight to master, leaving it broken for Tizen, before being moved onto `v3`.)

  **Why the same branch name in every repo:** there is no cross-repo atomic commit, and
  the contract has four mirrors (`CONTRACT.md`, `contract.py`, `contract.ts` ×2,
  `Contracts/*.cs`) that M6 changes at once. Matching names are what make "check out the
  milestone everywhere" possible; a mismatched checkout breaks the wire protocol at
  runtime, not build time. Don't branch per-repo-per-taste — that drift already happened
  once (`v3-harness-agent-board` vs `v3-m0-restructure`).

  A repo only gets a `v3` branch when a milestone actually touches it (cloud, chat-ui and
  the Tizen repos have none yet).
- **Commit identity:** author as `ashuksingh11`
  (`31301999+ashuksingh11@users.noreply.github.com`). **Push only when explicitly asked.**
- **Workflow (per the human):** plan=Opus · architecture/design=Fable · coding=Codex CLI
  · file browsing=Sonnet. Discuss before executing; **confirm before moving between
  phases — no phase jumps.** Every phase writes durable artifacts.
