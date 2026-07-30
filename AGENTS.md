# AGENTS.md — goal-flow-agents (coding-session guide)

Context for a coding session. This is the **docs-only / cross-cutting** repo for GoalFlow, a
two-tier goal-based agent POC for the Samsung Tizen Family Hub. It holds no runnable code; the
code repos are siblings under `~/ashu/git/`.

## The system in one paragraph

A **cloud agent** (Python/LangGraph — owns the goal: interpretation, household policy, the
human, board aggregation) and an **on-device agent** (.NET 8 + Semantic Kernel — owns the plan
and is the sole authority on local state and actuators) collaborate over a WebSocket **hub**
(the cloud) to turn a fuzzy, long-running goal of **any kind** into an adaptive,
approval-gated plan that keeps re-planning as the world moves. Six domains route: meal_plan,
guest_dinner, vacation_prep, birthday_party, grocery_cost, energy_saving. It is a general
**Goal Runtime**, not a meal app. Two gates: a deterministic **safety gate** (device code —
blocks) and an **approval gate** (the user, via the cloud — waits). Slogan: *"LLM plans, code
checks."* The world is faked; the mechanism is real.

## Docs

**There are two, and this is deliberate.**

- **[`docs/DESIGN.md`](docs/DESIGN.md)** ⭐ — the single design document: architecture, the
  harness, constraints, the wire, the surfaces, verification, and a brief per-version history
  in §10. There are no per-version design docs and no milestone plans; when behaviour changes,
  that file changes.
- **[`docs/FINAL_DEMO.md`](docs/FINAL_DEMO.md)** — how to run it, and the demo script prompt by
  prompt. **Run commands live only here**, so they cannot drift.

`docs/harness/` keeps the two original Samsung-side mocks (`agent-board.jpeg`,
`agentic-arch-execution-fw.png`). The input documents they came with were retired once
`DESIGN.md` §11 recorded what was built from them and what was not.

Each code repo has its own `AGENTS.md` (run commands, key files, gotchas) and `CODE_GUIDE.md`
(the walkthrough). Read the relevant one before coding there.

## The repos (all under ~/ashu/git/)

| Repo | Role |
|---|---|
| `goal-flow-cloud-agent` | the hub + goal graph. **Owns canonical `CONTRACT.md`** |
| `goal-flow-device-agent-ubuntu` | the device agent — **the source of truth** for device code |
| `goal-flow-device-agent-tizen` | Tizen port: copied core, different host. Re-synced per milestone |
| `goal-flow-agent-chat-ui` | the create-phase surface (understanding gate, plan, approvals) |
| `goal-flow-agent-board-ui` | **home** — the Agent Board, and Advance day |
| `goal-flow-agent-bixby-ui` | dev surrogate for Bixby: **where the user types** |
| `goal-flow-agent-tizen-ui` | NUI progress mirror on the fridge panel; parked at v4 |
| `goal-flow-agents` | this repo (docs) |

Ports are assigned by Vite in start order — read what each terminal prints rather than assuming
5173/5174.

## Conventions

- **`master` is trunk**, currently == v6; **v7 is in flight** on a `v7` branch in every repo. An integration branch per version (`v6`) with
  milestone branches off it, merged back `--no-ff` when that milestone's gate passes, then
  deleted. Small fixes go straight to the integration branch; branches are for milestones.
- **Push only integration branches and `master`** — milestone/feature branches stay local. Push
  only when explicitly asked.
- **Before merging `vN` → `master`, tag the pre-merge master `pre-vN`** and push the tag; it is
  the revert point. Never tag a name identical to a branch.
- **The same branch name in every repo.** There is no cross-repo atomic commit and the contract
  has four mirrors (`CONTRACT.md`, `contract.py`, `contract.ts` ×2, `Contracts/*.cs`) that a
  single milestone can change at once. Matching names are what make "check out the milestone
  everywhere" possible; a mismatched checkout breaks the wire at runtime, not at build time.
- **Commit identity:** author as `ashuksingh11`
  (`31301999+ashuksingh11@users.noreply.github.com`).
- **Gates, not vibes.** Run the whole suite, not the part you think you touched — and falsify a
  gate before trusting it. See `DESIGN.md` §9 for what exists on each side.
- **Confirm before moving between phases — no phase jumps.** Every phase leaves durable
  artifacts behind.
