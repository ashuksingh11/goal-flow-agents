# V5 — Harness Visualization ("watch the harness work")

## Why

The harnesses are the star of GoalFlow — Capability Manager, Pre-Check Engine, Safety
Policy Engine, Grounding, Planner, Task Manager, Approval, Monitor & Adapt. But in the v4
demo they were **invisible**: the agent streamed a coarse `phase` rail
(grounding → planning → checking) and a "watch it think" transcript, while the individual
engines ran silently *inside* those phases. Demo feedback: we couldn't *show* the thing
that makes GoalFlow GoalFlow.

v5 makes each engine **visible and sequential** — a **Harness Pipeline** that lights up
engine-by-engine ("now the Pre-Check Engine… now the Safety Policy Engine…"), each with a
live sub-line and a verdict, the active one glowing.

## What

- **Chat UI (create)** — a **Harness Pipeline** panel is the dominant region of the
  watch-it-think stage: Pre-Check → Capability Manager → Grounding → Planner → Safety
  Policy → Task Manager → Approval, checking off in fire order, the active engine glowing,
  the reasoning transcript slaved to it.
- **Presenter theater** — a full-bleed, projection-scale view of the same pipeline (big
  engine strip + a "NOW RUNNING" hero card), toggled by the chat UI's **Theater** switch.
- **Agent Board (run)** — a **Harness Ribbon** on the goal-detail page shows the *same*
  engines re-running during advance-day/monitoring (Monitor & Adapt → Safety → Task
  Manager), so the harness is visible both when a goal is created and every time the world
  changes under it.
- **Theme** — chat + presenter moved to a unified **light-grey** theme matching the board.

## How

The device already emits a single `Trace` → `agent_event` stream. v5 adds one new event
kind:

```
agent_event { event: "harness", payload: { module, status, note?, verdict?, grade? } }
```

- `module` ∈ `precheck | capability_manager | grounding | planner | safety | task_manager | approval | monitor_adapt`
- `status` ∈ `enter | active | pass | block | done | skip` (`active` lights it up; `pass`/`done` = green, `block` = red)

`Trace.HarnessAsync(...)` emits these; `GoalAgent.RunCoreAsync` calls it around each
engine at create time, and `GoalAgent.AdaptWithHarnessAsync` wraps **both** adaptation
branches (LLM steer + deterministic patch) so advance-day and trigger-event light the board
ribbon identically. The contract kind is mirrored in CONTRACT.md, the Python model, the C#
`AgentEvent.cs`, and both UIs' `contract.ts` (gated by `scripts/verify_mirrors.py`).

**Presenter mode is config/flag-gated.** The pipeline always renders in real time; only the
**demo dwell** (`HARNESS_DWELL_MS`, device config — env on Ubuntu, `goalflow.conf` on Tizen;
default `0` = off) and the full-screen theater switch on for a demo. With the dwell off,
real and verify timings are untouched.

## Where (files)

- Device (Ubuntu + Tizen, byte-identical core): `Contracts/AgentEvent.cs` (`HarnessModules`,
  `HarnessStatuses`, `Harness` kind), `Harness/Trace/Trace.cs` (`HarnessAsync`),
  `Agent/GoalAgent.cs` (instrumentation, `HarnessDwellMs`/`DwellAsync`, `AdaptWithHarnessAsync`);
  dwell wired via `Program.cs` (Ubuntu env) / `DeviceHost.cs` + `goalflow.conf` (Tizen).
- Contract mirrors: `goal-flow-cloud-agent/CONTRACT.md` + `models/contract.py`; chat-ui &
  board-ui `src/types/contract.ts`.
- Chat UI: `types/ui.ts` (`HarnessState`, `HARNESS_PIPELINE`, `reduceHarness`),
  `components/HarnessPipeline.tsx`, `components/HarnessTheater.tsx`, `App.tsx` reducer +
  stage wiring, light-grey retheme in `styles.css`.
- Board UI: `state/reducer.ts` (`HarnessMap`, `RIBBON_ENGINES`, harness fold),
  `components/HarnessRibbon.tsx`, `GoalDetail.tsx`.

## Demo

Start cloud + device (`HARNESS_DWELL_MS=1500`) + chat UI + board UI. Speak a goal (Bixby /
input surface) → confirm understanding on the chat surface → **watch the Harness Pipeline
light up engine-by-engine**, Safety Policy glowing as it enforces `constraints.hard`. Approve
→ the board takes over; **Advance day** → the **Harness Ribbon** shows Monitor & Adapt →
Safety → Task Manager re-running as the plan adapts to the world. Toggle **Theater** for the
projection view.
