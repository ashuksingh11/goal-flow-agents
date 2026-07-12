# GoalFlow — Documentation

Start here. These docs cover the whole GoalFlow POC (a two-tier goal-based agent demo for the
Samsung Tizen Family Hub).

> **v2 is current.** GoalFlow was rebuilt into a **general goal-based agent** (SK plugins + auto
> function-calling, advanced LangGraph, LLM-only, wow UI, two domains: meal + guest dinner). Start with
> the v2 docs below. The v0/v1 docs (`SYSTEM_OVERVIEW`, `DEMO_RUNBOOK`) are kept for history.

## Cross-cutting (this folder)

- **[FINAL_DEMO.md](FINAL_DEMO.md)** ⭐ — the **final demo run-sheet** (v2): setup, the two-act demo
  (meal + guest dinner) with narration, presenter mode, headless smoke test, and troubleshooting.
- **[V2_DESIGN_PROPOSAL.md](V2_DESIGN_PROPOSAL.md)** — the v2 architecture: the 11 domain-agnostic
  **harness modules**, capability vs steering modules, the use-case catalog, and what changed from v1.
- **[UX_CONFIRM_UNDERSTANDING.md](UX_CONFIRM_UNDERSTANDING.md)** — current design spec: the
  confirm-understanding HITL gate (Understanding card) between grounding and planning.
- **[UX_EVENT_REDESIGN.md](UX_EVENT_REDESIGN.md)** — current design spec: the event-driven meal
  demo (World-events chip strip, `trigger_event`, morph-the-day-card animation, cloud→device
  handoff visualization).
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

Three terminals — see [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) for detail:

```bash
# 1) cloud (hub)
cd goal-flow-cloud-agent && source .venv/bin/activate && uvicorn goalflow_cloud.server:app --host 127.0.0.1 --port 8000
# 2) device
cd goal-flow-device-agent-ubuntu && WS_URL=ws://localhost:8000/ws dotnet run -- --connect
# 3) UI
cd goal-flow-agent-chat-ui && npm run dev -- --host 127.0.0.1 --port 5173
# then open http://127.0.0.1:5173
```
