# GoalFlow — Documentation

Start here. These docs cover the whole GoalFlow POC (a two-tier goal-based agent demo for the
Samsung Tizen Family Hub).

## Cross-cutting (this folder)

- **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** — architecture, the three services, the wire protocol
  (Contract v0), the end-to-end message flow (with diagrams), and the device harness pipeline.
- **[DEMO_RUNBOOK.md](DEMO_RUNBOOK.md)** — how to deploy each service, run the demo (browser +
  headless), a suggested run-sheet, and **troubleshooting** (LLM/429, WebSocket, build, data reset).

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
