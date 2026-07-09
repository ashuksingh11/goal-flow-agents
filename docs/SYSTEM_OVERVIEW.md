# GoalFlow — System Overview

A proof-of-concept for **goal-based agents** on a Samsung Tizen Family Hub. A user gives a
fuzzy, high-level goal ("help my family eat healthier this week and reduce food waste"); a
**cloud agent** and an **on-device agent** collaborate, with a **human in the loop**, to turn
it into an adaptive, approval-gated weekly dinner plan.

> POC ethos: **"fake the world; make the mechanism real."** The product APIs, memory, and "the
> week" are mocked; the orchestration pattern (two tiers, a clean contract, negotiation, HITL,
> live adaptation) is real.

---

## The three services

| Service | Repo | Stack | Role |
|---|---|---|---|
| **Chat UI** | `goal-flow-agent-chat-ui` | React + Vite + TypeScript | The tablet client. Chat input, plan reveal, HITL approvals, demo controls, presenter mode. |
| **Cloud agent** | `goal-flow-cloud-agent` | Python 3.11+, FastAPI, LangGraph | The **hub**. Owns conversation + memory; turns the goal into a Task Contract via an LLM; relays everything. |
| **Device agent** | `goal-flow-device-agent-ubuntu` | .NET 8, Semantic Kernel | The **executor**. Sole authority on local state; runs the harness pipeline; the only thing that "touches actuators". |

A fourth repo, `goal-flow-device-agent-tizen`, is a placeholder for the future Tizen C#/.NET port.

---

## Topology

```
   ┌─────────────────┐        WS         ┌──────────────────────┐        WS        ┌────────────────────┐
   │   Chat UI (TS)  │ ───────────────►  │  Cloud agent (Python)│ ──────────────►  │ Device agent (.NET)│
   │  tablet client  │ ◄───────────────  │   FastAPI WS HUB     │ ◄──────────────  │  harness pipeline  │
   └─────────────────┘                   └──────────────────────┘                  └────────────────────┘
        role: ui                              cloud is the server                       role: device
```

- **The cloud is the only WebSocket server.** The UI and the device each open **one outbound
  WS connection** to the cloud (`ws://<cloud>:8000/ws`) and register a role with a `hello` frame.
- **The UI and the device never talk directly.** Everything routes through the cloud, because the
  cloud owns conversation + memory.
- Device opens outbound WS (no inbound ports on the Hub) — works on both Linux dev and Tizen.

## Two invariants that define the design

1. **Cloud owns talk/memory; device owns local truth.** The cloud decides *what/why* (the
   contract); the device decides *how* (the concrete plan) because only it knows current
   inventory/calendar. Planning is a negotiation, not owned by one side.
2. **Two distinct gates, kept separate in code:**
   - **Safety gate** = deterministic *code on the device*. Checks the plan against
     `constraints.hard` (allergens/dietary/medical) and **blocks** on violation.
   - **Approval gate** = the *user via the cloud*. The device emits side-effects as
     **proposals, not actions**, and **waits**. Nothing executes until an `approval` returns.
   - Slogan: **"LLM plans, code checks."** The `Planner` and `SafetyGate` are separate classes;
     the fallible/probabilistic planner never runs the absolute/deterministic safety check.

---

## The wire protocol (Contract v0)

Canonical spec: [`goal-flow-cloud-agent/CONTRACT.md`](../../goal-flow-cloud-agent/CONTRACT.md).
Mirrored as TypeScript types (`goal-flow-agent-chat-ui/src/types/contract.ts`) and C# records
(`goal-flow-device-agent-ubuntu/src/GoalFlow.Device/Contracts/`).

- Transport: **WebSocket**, JSON text frames. Field `type` discriminates every message.
- Every task message carries `goal_id`; device↔cloud messages carry `correlation_id`
  (dedupe key; also correlates an approval back to its proposal).

| `type` | Direction | Purpose |
|---|---|---|
| `hello` / `hello_ack` | client → cloud / cloud → client | Register role (`ui` or `device`). |
| `user_goal` | UI → cloud | The fuzzy goal text. |
| `dispatch` | cloud → device | The **Task Contract** (objective, scope, time window, `constraints.hard`/`soft`, optimization, autonomy). `constraints.hard` is the ONLY thing the safety gate reads. |
| `plan_ready` | device → cloud | The plan + proposals + `safety` result + `impact` metrics + `knew`(added by cloud). |
| `present_plan` | cloud → UI | Relayed plan for rendering (adds `knew` personalization). |
| `proposal` | device → cloud → UI | An adaptation proposal (the Wednesday-football beat). |
| `approval` | UI → cloud → device | User's decision(s) on proposals. |
| `status` | device → cloud → UI | Lifecycle updates + sustain-tick day summaries + execution results. |
| `control` | UI → cloud → device | Demo controls: `advance_day`, `reset`. |

Task-status lifecycle: `created → planning → awaiting_approval → executing → adapting → done`
(plus `monitoring` during the sustain loop).

---

## End-to-end flow (happy path)

```mermaid
sequenceDiagram
    participant U as Chat UI
    participant C as Cloud (LangGraph hub)
    participant D as Device (harness pipeline)

    Note over U,D: startup — UI and Device each WS-connect to Cloud and send hello
    U->>C: user_goal { text }
    C->>C: graph: ambiguity → memory → decompose (LLM builds contract;<br/>hard constraints injected deterministically from memory)
    C->>D: dispatch (Task Contract)
    D->>D: Grounding → Planner → SafetyGate (code) → ApprovalBroker
    D->>C: plan_ready { plan, proposals, safety, impact }
    C->>U: present_plan { …+ knew }
    U->>C: approval { decisions:[{proposal_id, approved:true}] }
    C->>D: approval
    D->>D: EffectExecutor performs the side-effect (idempotent)
    D->>C: status { executing → done, executed:[…] }
    C->>U: status  (UI shows "5 items added to shopping list")

    Note over U,D: later — the adaptation beat (virtual clock)
    U->>C: control { advance_day }
    C->>D: control
    D->>D: sustain tick: reconcile inventory, check calendar, ChangeWatcher
    D->>C: status { monitoring, day, material:false }   (quiet days)
    C->>U: status
    Note over D: on Wednesday: football event overlaps prep window → MATERIAL
    D->>C: proposal { adapting, trigger:"football Wed 18:00 — prep window shrinks" }
    C->>U: proposal
    U->>C: approval (the "adapt" rung)
    C->>D: approval
    D->>C: status { done, executed:["prep reminder created"] }
    C->>U: status
```

---

## The device harness pipeline (the core IP)

The device is a reusable execution substrate — **sense → decide → gate → act → sustain**, with a
cross-cutting trace. Each harness is an interface with a swappable implementation.

| Phase | Harness | Responsibility |
|---|---|---|
| Sense | `Grounding` + adapters (`Inventory/Calendar/Recipe/ShoppingList/Reminder`) | Assemble a `WorldState` from mock JSON (expiry-aware). |
| Decide | `IPlanner` → `RulesPlanner` (default) / `LlmPlanner` (SK+OpenRouter) / `ScriptedPlanner` | Contract + world-state → candidate plan. Swappable via `--planner`. |
| Gate | `SafetyGate` | **Deterministic code** check vs `constraints.hard`; blocks + returns violations. |
| Gate | `ApprovalBroker` | Freezes side-effects as proposals; tracks pending → approved → executed; correlates by id. |
| Act | `EffectExecutor` | Performs approved effects **idempotently** (dedupe on `correlation_id:proposal_id`). |
| Sustain | `Scheduler` + `ChangeWatcher` | Fire the sustain loop off the **virtual clock**; apply the materiality policy; adapt only when material. |
| Cross-cut | `Trace` (+ `IClock`) | Structured log of every step (feeds the presenter feed). Never reads wall-clock — only the virtual clock. |

---

## Mock world (the scripted scenario)

- **Family memory** (`goal-flow-cloud-agent/data/memory/family_profile.json`): hard = `no_pork`;
  soft = dislikes mushrooms, prefer more vegetables/protein; context = Aarav's football Wed 18:00.
- **Device seed data** (`goal-flow-device-agent-ubuntu/data/`): `inventory.json` (spinach/yogurt
  expiring), `calendar.json` (Wed football), `recipes.json` (5 Indian-veg dinners with
  ingredient/constraint flags), `shopping_list.json`/`reminders.json` (start empty),
  `sample-contract.json` + `golden-plan_ready.json` (fixtures).
- **Virtual clock** anchored at `2026-07-12`; demo week = Mon `2026-07-13` → Fri `2026-07-17`.

For per-repo code walkthroughs see each repo's `CODE_GUIDE.md`. To run the demo see
[`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md).
