# AGENTS.md — goal-flow-agents (coding-session guide)

Context for an AI/coding session. This is the **docs-only / cross-cutting** repo for
GoalFlow — a two-tier, goal-based agent POC for the Samsung Tizen Family Hub. It holds
no runnable code; the five code repos are siblings under `~/ashu/git/`.

## The system in one paragraph

A **cloud agent** (LangGraph/Python, owns conversation + memory + human-in-the-loop)
and an **on-device agent** (.NET 8 + Semantic Kernel, sole authority on local state +
actuators) collaborate over a WebSocket **hub** (the cloud) to fulfil a fuzzy,
long-running goal of **any kind** — meals, a birthday party, vacation prep, grocery cost,
energy saving (the five locked v3.4 use cases, + guest dinner) — into an adaptive,
approval-gated plan that keeps re-planning as the world changes. It is a general **Goal
Runtime**, not a meal app. **Two React surfaces**: a chat UI where you CREATE a goal, and
the **Agent Board** where a goal LIVES (goals-first cards, the global Advance-day
simulation). UI and device never talk directly. Two gates: a deterministic **safety gate**
(device code, blocks) and an **approval gate** (the user via the cloud, waits). Slogan:
*"LLM plans, code checks."* The POC proves the orchestration pattern; the world is faked,
the mechanism is real.

## The repos (all under ~/ashu/git/)

- `goal-flow-cloud-agent` — Python/FastAPI/LangGraph hub. **Owns canonical `CONTRACT.md`.**
- `goal-flow-device-agent-ubuntu` — .NET 8/SK device brain. **Current source of truth** for the device.
- `goal-flow-agent-chat-ui` — React/Vite/TS chat UI (create a goal; port 5173).
- `goal-flow-agent-board-ui` — React/Vite/TS Agent Board (run a goal; port 5174).
- `goal-flow-device-agent-tizen` — Tizen deployment of the device agent. **In sync with ubuntu**
  (re-synced 2026-07-20, v3.6.2); a thin platform port of the byte-identical core (see its AGENTS.md).
- `goal-flow-agents` — this repo (docs).

Each code repo has its own `AGENTS.md` with run commands, key files, and gotchas —
read the relevant one before coding there.

## Docs in this repo (current vs historical)

- **Current:** `docs/V3_DESIGN_PROPOSAL.md` ⭐ (the canonical v3 architecture; its §12
  amendment log records every shipped milestone through v3.6), and `docs/FINAL_DEMO.md`
  (the v3.6 presenter run-sheet). `docs/UX_CONFIRM_UNDERSTANDING.md` is still current (the
  confirm-understanding gate). `docs/V2_DESIGN_PROPOSAL.md` is the prior architecture,
  superseded by v3 §3.
- **Superseded:** `docs/UX_EVENT_REDESIGN.md` (the per-goal event-driven meal week /
  EventStrip — v3.2 removed it for a global Advance day; kept for design history).
- **Historical (v1, superseded):** `docs/SYSTEM_OVERVIEW.md`, `docs/DEMO_RUNBOOK.md`
  — kept for reference; they describe the retired v1 clock-advance / rules-planner
  design. Banner-flagged in-file.
- **Archival brainstorm:** `GoalFlow-discussions/{claude,gpt}/*.md` — design input, not
  frozen spec.
- `docs/README.md` indexes all of the above.

## The v3 shape (know these — the docs above have the detail)

1. **Confirm-understanding gate** — before planning, the cloud shows its read
   (objective / constraints / thought / summary); the user Confirms (or Declines).
   Wire: `understanding` → `understanding_response`; cloud node `present_understanding`.
2. **Board-centric flow (v3.1) + global Advance day (v3.2)** — chat CREATES a goal; once the
   plan is approved the **Agent Board** runs it. World simulation is ONE global **Advance
   day** on the main board (a goal-less `control` → the device advances its clock once, fans
   out over every active goal, and returns a `day_advanced` summary). This replaced the
   earlier per-goal EventStrip.
3. **Five locked use cases (v3.4) + generic planner (v3.5)** — six domains route
   (meal_plan, guest_dinner, vacation_prep, birthday_party, grocery_cost, energy_saving); the
   device planner takes its plan shape from the contract's domain, not a hardcoded meal week.
4. **Goals-first board cards (v3.6)** — each card leads with the outcome and tells the goal's
   story in three lines: ✓ done · ⏳ waiting · ➡ next.

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
