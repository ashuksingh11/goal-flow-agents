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
- Chat UI: `types/ui.ts` (`HarnessState`, `HARNESS_PIPELINE`, `reduceHarness`, pacing:
  `enqueueHarness`/`drainHarness`/`settleHarness`), `components/HarnessPipeline.tsx`
  (full + collapsed ribbon), `components/HarnessTheater.tsx`, `App.tsx` reducer +
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

## Follow-up: the last three engines flashed past (chat UI pacing)

Demo feedback after v5 shipped: the pipeline order was right, but Safety Policy Engine, Task
Manager and Approval appeared to "work" for no time at all. Cause is real and structural, not
a UI bug — those engines' work happens EARLIER than their beats:

- **Safety** vets every tool call inside `SafetyFilter.OnFunctionInvocationAsync`, i.e. all
  the way through grounding and planning; the beat at the end only reports `GateFor` /
  `ViolationsFor`.
- **Task Manager**'s DAG comes from `DecomposeAsync`, which runs BEFORE grounding (and
  `_tasks.CreateGoal` runs after the Approval beat).
- **Approval** registers proposals just before its own beat — microseconds.

So each emits `active` + resolve back-to-back with only the optional dwell in between; at the
default `HARNESS_DWELL_MS=0` that is the same millisecond. Measured on a real run: all six
tail beats inside **10 ms**, `plan_ready` 41 ms later, and `present_plan` then UNMOUNTED the
whole panel — the three engines were never seen at all.

Fixed in the chat UI only, and only in WHEN we paint (order, verdicts and total latency stay
exactly as the device reported them):

1. **Render floor** — beats queue in `HarnessState.queue` and a timer drains them one at a
   time (`HARNESS_ACTIVE_FLOOR_MS` 550 ms for an `active`, `HARNESS_RESOLVE_STEP_MS` 150 ms
   after a resolve). Grounding/Planner are never delayed: their real gap already exceeds the
   floor. Cost ≈1 s at the head, ≈1.6 s at the tail of a 60–90 s plan.
2. **Outlive the plan** — the panel stays mounted past `present_plan` until the queue drains
   plus `HARNESS_SETTLE_MS` (900 ms), then collapses to a one-line glyph ribbon
   ("7/7 engines cleared") above the plan hero.

Live-verified twice at `HARNESS_DWELL_MS=0` (meal + energy goals): each of the three engines
now holds `working…` for ~550 ms and resolves visibly, 2.85 s of watchable sequence from
beats emitted in ~10 ms. Rejected alternative: moving the beats to wrap the real call sites —
it would make Safety strobe *concurrently* with Grounding/Planner, split Task Manager into two
visits straddling Approval, and still leave Approval and Capability Manager with no duration
to show, so the pipeline would stop being a readable sequence.

Board ribbon is unaffected: on the adapt path `Monitor & Adapt` wraps a real LLM call, and its
Safety / Task Manager beats are resolve-only (no `active`), so nothing flashes.


## Superseded on the chat surface by v5.1

The pipeline panel described above (a 7-row list beside the reasoning transcript, under the
phase rail) was replaced on the chat surface by the **working column** — see
[V5_1_WORKING_COLUMN.md](V5_1_WORKING_COLUMN.md). The engines, their order, their verdicts and
the beat contract are unchanged; what changed is that resolved engines collapse into permanent
receipts, exactly one focus card holds the transcript that produced it, and the column's height
is conserved so the screen never scrolls. The render floor and the settle window described in
the follow-up above still exist, but they are now polish rather than the only thing keeping the
tail engines visible. The presenter theater and the board ribbon are unchanged.
