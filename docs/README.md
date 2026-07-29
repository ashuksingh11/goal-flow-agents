# GoalFlow — Documentation

Start here. These docs cover the whole GoalFlow POC (a two-tier goal-based agent demo for the
Samsung Tizen Family Hub).

> **v3 is current and SHIPPED (through v3.6).** GoalFlow is a **multi-goal agent with an explicit
> harness**: five first-class components (Capability Manager, Safety Policy Engine, Pre-check Engine,
> Task Manager, Product API Adapter), device-side two-altitude planning, and **Agent Board** — a
> glanceable dashboard over every running goal. M0–M9 landed, then v3.1 (board-centric flow), v3.2
> (global Advance-day world tick), v3.4 (**five locked demo use cases** — a general Goal Runtime, not
> "AI meal planning"), v3.5 (the planner is generic per-domain, not meal-shaped), and v3.6 (goals-first
> board cards). Start with `V3_DESIGN_PROPOSAL.md`; its §12 amendment log records every shipped
> milestone. **v2 is the prior architecture** (`V2_DESIGN_PROPOSAL.md`); the v0/v1 docs
> (`SYSTEM_OVERVIEW`, `DEMO_RUNBOOK`) are kept for history.

## Cross-cutting (this folder)

- **[V3_DESIGN_PROPOSAL.md](V3_DESIGN_PROPOSAL.md)** ⭐ — **the v3 architecture** (current): the five
  harness components, how v2's 11 modules reconcile onto them, grades (A0/A1/A2/AX), multi-goal
  concurrency, the contract-v3 delta, Agent Board, the use-case lineup, and the M0–M9 roadmap.
- **[harness/](harness/)** — the v3 **architecture input**: the harness discussion doc, the device-agent
  TDS, and the Agent Board / execution-framework mocks. Design input, not frozen spec.
- **[V5_1_WORKING_COLUMN.md](V5_1_WORKING_COLUMN.md)** ⭐ — **current**: the chat surface is one
  working column (receipts / one focus card holding the transcript / ghosts, then the plan
  landing into reserved slots). Height conservation, honest per-engine durations, the paced plan
  reveal + the `plan_progress.total` contract addition, and the transcript JSON fix.
- **[V6_CONSTRAINTS.md](V6_CONSTRAINTS.md)** 🚧 — **design, not yet built**: constraints become a
  sourced, scoped, expiring model that resolves *per goal* — so a vacation goal is constrained like
  a vacation (travel cap + away window), not like a meal week ($120 grocery cap). Kills the
  cloud/device duplication of household truth, adds the two constraints that make vacation and
  energy goals genuinely enforceable, then the household budget envelope (cross-goal) and
  capture-from-chat with a confirmation gate. Four milestones, M1–M4.
- **[V5_PLAN.md](V5_PLAN.md)** — v5: making the harness visible (Harness Pipeline, presenter
  theater, board ribbon, light-grey theme) and the follow-up that fixed the tail engines
  flashing past. Superseded on the chat surface by V5_1.
- **[V4_PLAN.md](V4_PLAN.md)** / **[V4_1_ARCHITECTURE.md](V4_1_ARCHITECTURE.md)** /
  **[V4_2_PLAN.md](V4_2_PLAN.md)** — v4: the Bixby entry point + surface-aware delivery, and
  advance-day date targeting with real dates.
- **[FINAL_DEMO.md](FINAL_DEMO.md)** ⭐ — the **final demo run-sheet** (v3.6): setup, the act-by-act
  demo (chat creates a goal → board runs it → global Advance day → the five-use-case range on
  goals-first cards) with narration, presenter mode, headless smoke test, and troubleshooting.
- **[V2_DESIGN_PROPOSAL.md](V2_DESIGN_PROPOSAL.md)** — *(prior architecture)* the v2 design: the 11
  domain-agnostic **harness modules**, capability vs steering modules, the use-case catalog, and what
  changed from v1. Superseded by v3 §3, which maps the 11 onto the five components.
- **[UX_CONFIRM_UNDERSTANDING.md](UX_CONFIRM_UNDERSTANDING.md)** — current design spec: the
  confirm-understanding HITL gate (Understanding card) between grounding and planning.
- **[UX_EVENT_REDESIGN.md](UX_EVENT_REDESIGN.md)** — *(superseded by V3_DESIGN_PROPOSAL §12l, v3.2)* the
  per-goal event-driven meal demo (World-events chip strip, `trigger_event`). v3.2 removed the per-goal
  EventStrip and replaced it with one global **Advance day** on the main board; kept for design history.
- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) — *(v1, historical)* original architecture + Contract v0.
- [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) — *(v1, historical)* the milestone-wise runbook.

## Per-repo code guides (in each repo)

- `goal-flow-cloud-agent/CODE_GUIDE.md` — the LangGraph WS hub (Python).
- `goal-flow-device-agent-ubuntu/CODE_GUIDE.md` — the harness pipeline (.NET / Semantic Kernel).
- `goal-flow-agent-chat-ui/CODE_GUIDE.md` — the tablet chat UI (React/TS).

## Canonical references

- `goal-flow-cloud-agent/CONTRACT.md` — the frozen wire protocol (source of truth).
- Design discussion notes (background, not final truth): `../GoalFlow-discussions/`.

## Quick start

**Run commands live in ONE place — [FINAL_DEMO.md](FINAL_DEMO.md) § "Run".** It has
the canonical setup, the local (one-machine) commands, the across-machines
(cloud / tablet / Tizen) variant, and the headless device sims. Don't copy run
commands into other docs — link to that section instead, so they can't drift.

```bash
# 1) cloud   cd goal-flow-cloud-agent        && source .venv/bin/activate && ./run.sh
# 2) device  cd goal-flow-device-agent-ubuntu && dotnet run --project GoalFlow.Device.csproj -- --connect
# 3) UI      cd goal-flow-agent-chat-ui       && npm run dev
# then open http://localhost:5173
```
