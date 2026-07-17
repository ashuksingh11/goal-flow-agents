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

- **Branching (v3 onward): one branch per MILESTONE, the SAME name in every repo it
  touches** — `v3-m1-safety-policy`, `v3-m2-task-manager`, … Merge to `master` with
  `--no-ff` when that milestone's gate passes, then delete the branch. So `master`
  always equals the last completed milestone and the demo is always runnable from it,
  and each milestone is one revertable anchor in history.
  **Why the same name everywhere:** there is no cross-repo atomic commit, and the
  contract has four mirrors (`CONTRACT.md`, `contract.py`, `contract.ts` ×2,
  `Contracts/*.cs`) that M6 changes at once. Matching names are what make
  "check out the milestone everywhere" possible; a mismatched checkout silently breaks
  the wire protocol. Do not branch per-repo-per-taste — that drift already happened once
  (`v3-harness-agent-board` vs `v3-m0-restructure`) and was cleaned up at the M0 merge.
- **Commit identity:** author as `ashuksingh11`
  (`31301999+ashuksingh11@users.noreply.github.com`). **Push only when explicitly asked.**
- **Workflow (per the human):** plan=Opus · architecture/design=Fable · coding=Codex CLI
  · file browsing=Sonnet. Discuss before executing; **confirm before moving between
  phases — no phase jumps.** Every phase writes durable artifacts.
