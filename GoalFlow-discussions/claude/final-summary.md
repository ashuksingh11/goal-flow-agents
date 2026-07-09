
# Family Hub Goal-Based Agents — POC Design Brief

> **Purpose of this doc.** A handoff for a coding agent. It captures the shared understanding and current design _direction_ from a design discussion. It is **not a frozen spec** — the hard implementation decisions (exact schemas, LLM-vs-rules, state-machine details, library versions) are intentionally left open to refine during build. Treat everything here as working direction, not mandate.

---

## 1. What we're building

A proof-of-concept for **goal-based agents** on a **Samsung Family Hub (Tizen)**: a two-tier system where a **cloud agent** and a **device agent** collaborate, with a **human in the loop**, to fulfil a fuzzy high-level goal over a **long-running** operation.

**Driving use case.** On the Family Hub, a user gives a fuzzy goal — e.g. _"help my family eat healthier this week and reduce food waste."_ The cloud agent resolves ambiguity, recalls the family's context, and turns the goal into a structured task. The device agent executes it against local state (inventory, calendar, meal planner, shopping list) and returns a plan plus proposals. The user approves. Over the week, the system adapts to changes (e.g. a child's football match compressing a prep window) — always keeping the human in the loop.

**Goal of the POC.** Prove the **orchestration pattern** (two tiers, a clean contract, negotiation, human-in-the-loop, live adaptation). It is **not** production-grade. Fake the world; make the _mechanism_ real.

**Stack (direction).** Cloud agent = **LangGraph** (Python). Device agent = **Semantic Kernel** (.NET; runs on Tizen).

---

## 2. Core architecture & principles

- **Cloud** orchestrates, talks, and remembers. **Device** is the **sole authority on local state** and the **only thing that touches actuators**.
- **Planning is a negotiation:** the cloud sets the _what/why_ (the contract); the device produces the _how_ (the concrete plan) because only it knows current inventory/calendar.
- **Cloud fully resolves ambiguity before dispatch.** The device receives a clean, complete contract and never sees the clarifying dialogue.
- **Two genuinely separate agents**, not one process pretending to be two. The _interface between them is the thing being proven_. (Using two different frameworks helps keep the boundary real.)
- **The device UI and the device agent must never shortcut to each other** — everything routes through the cloud, since the cloud owns conversation + memory.

---

## 3. The two agents — responsibilities

**Cloud agent (understand · remember · talk)**

- Owns the conversation; takes the fuzzy goal.
- Resolves ambiguity (for the POC: a single scripted confirmation, not a live multi-turn loop).
- Holds the family profile + memory; retrieves relevant context.
- Decomposes the goal into the **task contract** (what/why), assigns the goal ID, dispatches it.
- Relays the device's plan / proposals / questions to the user, collects approvals, presents results, and owns the adaptation conversation.

**Device agent (execute · local truth)**

- Receives the contract; drives the task lifecycle.
- Gathers local state, produces the concrete plan, runs the safety gate.
- Emits the plan and any side-effects as **proposals (not actions)**.
- On approval, executes against actuators and updates status.
- On a (scripted) world change, proposes an adaptation back up.

---

## 4. Device agent harnesses (the core IP)

A reusable **execution substrate** — sense, decide, gate, act, sustain, explain — instantiated here for meals but general to any goal-contract. Grouped by phase:

|Phase|Harness|Role|
|---|---|---|
|Orchestrate|**Task manager**|Creates the task, assigns the goal ID, drives the status lifecycle.|
|Sense|**Pre-check**|Validates access/permissions to the sources.|
|Sense|**Capability manager**|Discovers available local + cloud APIs.|
|Sense|**Product API adapters**|Typed clients for recipe/inventory/calendar APIs.|
|Sense|**Grounding / world-state assembler**|Normalises retrieved data into one coherent state object for the planner.|
|Decide|**Planner**|Turns contract + world-state + constraints into a candidate plan. LLM-backed, swappable.|
|Decide|**Safety gate**|**Deterministic code** check of the plan against the hard-constraint block; blocks on violation.|
|Gate|**Approval broker**|Freezes side-effects as proposals; tracks pending/approved/rejected/expired; correlates the user's decision back.|
|Act|**Effect executor**|Performs approved effects **idempotently** (dedupe on `correlation_id`); records what was done.|
|Sustain|**Scheduler / temporal engine**|Fires time-based actions off the **virtual clock**.|
|Sustain|**Change / materiality watcher**|Detects world changes, applies a materiality policy, re-invokes the loop only when material.|
|Cross-cutting|**Trace / audit log**|Structured record of every decision, tool call, gate outcome, state change. Doubles as the demo activity feed.|

**Critical guardrail:** keep **Planner** and **Safety gate** separate. The planner is probabilistic/fallible; the gate is code and absolute. Never let the planner perform the safety check.

**Build effort (direction, not mandate):**

- _Full logic:_ task manager, grounding, planner, safety gate, approval broker, effect executor, change watcher.
- _Real but simple:_ scheduler (minimal virtual-clock tick), trace/audit (structured logger).
- _Honest stubs:_ pre-check (pass-through that logs "access validated"), capability manager (static registry). Product adapters = real interface + mocked data.
- Do **not** build separate harnesses for budget/quiet-hours or graceful-degradation yet — leave as named extension points.

---

## 5. The wire protocol

Transport-agnostic JSON. Both agents agree on these shapes; `type` discriminates the message.

**Task contract (cloud → device).** The `constraints.hard` block is the _only_ thing the safety gate reads.

```json
{
  "goal_id": "meal-2026-w29",
  "objective": "healthier family dinners, less food waste",
  "scope": { "meal": "dinner", "days": ["Mon","Tue","Wed","Thu","Fri"] },
  "time_window": { "start": "2026-07-13", "end": "2026-07-17" },
  "constraints": {
    "hard": { "allergens": [], "dietary": ["no_pork"], "medical": [] },
    "soft": { "dislikes": ["mushrooms"], "prefer": ["more_vegetables","more_protein"] }
  },
  "optimization": ["reduce_processed", "reduce_waste"],
  "autonomy": "propose_all",
  "context_hints": { "notes": "son has sports Wednesday" },
  "reply_to": "kb/device/meal-2026-w29"
}
```

**Result envelope (device → cloud).** Recurs as `plan_ready`, `proposal`, `status`, etc. — same shape.

```json
{
  "type": "plan_ready",
  "goal_id": "meal-2026-w29",
  "correlation_id": "disp-001",
  "task_status": "awaiting_approval",
  "payload": {
    "plan": [ { "day": "Mon", "dish": "spinach & paneer rice bowl", "why": ["more_vegetables","uses_inventory"] } ],
    "proposals": [ { "proposal_id": "p1", "action": "add_to_shopping_list", "items": ["bell peppers","lentils","yogurt"], "requires_approval": true } ],
    "safety": { "gate": "passed", "hard_violations": [] }
  }
}
```

**Downward approval (cloud → device):**

```json
{ "type": "approval", "goal_id": "meal-2026-w29", "correlation_id": "evt-014",
  "payload": { "decisions": [ { "proposal_id": "p7", "approved": true } ] } }
```

- Two memory stores feed the contract: a small **authoritative hard-constraints profile** (allergens/medical/hard dietary — _never_ retrieved semantically) and a large **fuzzy soft-preference/episodic memory** (biases the planner only). For the POC both can be tiny JSON files.
- Surface `safety.gate` up to the UI ("checked ✓") — it's a cheap, high-trust moment.
- Task status lifecycle (direction): `created → planning → awaiting_approval → executing → adapting → done`.

---

## 6. Communication channel

**WebSocket** (chosen over MQTT: Tizen has no native MQTT; MQTT there means cross-compiling a library like Paho — friction we don't want for a demo).

- The **device opens an outbound WebSocket to the cloud** at startup — no inbound ports on the Hub, no broker. Full-duplex → device-initiated push works natively.
- Device side: `System.Net.WebSockets.ClientWebSocket` (BCL — works on Linux dev and Tizen).
- Cloud side: the cloud is the **WS server** (Python `websockets` or FastAPI), holding two connections: one to the tablet UI, one to the device.
- Carry the same JSON envelopes as WS text frames; route on `type`; dedupe on `correlation_id`. Reconnect on drop.

---

## 7. Deployment & dev approach

- **Dev Linux-first:** build the device agent as a **Linux .NET console app** (for fast dev/test with a coding assistant), then **port to Tizen**. Keep anything Tizen-specific (device APIs, local storage) behind **injectable interfaces** so harness logic stays pure and portable — only adapter implementations swap.
- **Demo runtime:** cloud agent on a laptop (also hosts the operator/control panel); device agent on the real Family Hub, with the Linux build as a **fallback** (a one-line endpoint swap, thanks to the clean boundary). Everything on a **local intranet**.

---

## 8. Simulating the "week" (demo mechanics)

The operation is week-long, but the demo compresses it:

- **Virtual clock** the device reads instead of wall-clock time. _Discipline: never call `datetime.now()` on the device — read the virtual clock, or the demo desyncs._
- **Scripted event injection:** 2–3 pre-authored world events (calendar gains a match; an item shows as consumed), fired on cue.
- **Demo control panel** on the laptop: the clock, an "advance day" button, and a button per event.
- **Prove the loop once + one adaptation event**, not seven days. Seven cycles re-run the same mechanism.

**Reliability simplifications (direction):**

- Pin the LLM to the scripted scenario (low temperature, cached/canned outputs, deterministic). Optionally make the device planner rules-based for the demo and keep the visible "intelligence" in the cloud.
- Seed and **reset** the world (fixed inventory/calendar, one-button reset for re-runs).
- Two acts: Act 1 (goal → plan → approve → execute) fully live; Act 2 (adaptation) can be lightly scripted / narrated from the trace.

---

## 9. UX — the two-screen setup

Split the UI across two physical screens to make the two-tier architecture **visible**:

- **Tablet (Galaxy Tab)** = the **cloud agent's face**: conversation, the plan, **all approvals**, day-by-day interaction. Fully interactive, in-hand.
- **Family Hub screen** = the **device agent's face**: **display-only**, glanceable from across the room, showing the device _working through its stages_.

Principles:

- **Only one screen is the "star" at a time** — choreograph the focus transfer. The **cloud→device hand-off is a physical stage moment** (tablet hands off → fridge lights up). It also fills the planning latency with "watch it think."
- The Hub must feel like the appliance **doing** (checking inventory, planning, running the safety gate), **not reporting a log**.
- **Degrade path:** if Hub coordination hiccups live, the device stages collapse onto the tablet inline and the demo still runs end-to-end.
- Raw machinery (harness log, JSON, message flow) lives on the **operator/second screen** for technical narration, keeping the product surfaces clean.

**Plan-reveal screen layout:** the plan is the hero; the personalization line ("what it knew") and the safety chip are _evidence_, not chrome; a single clear approval CTA.

---

## 10. Demo run-sheet (10 beats, 2 screens)

★ = where the room's eyes should be. Hand-offs (beats 4 and 9) carry the whole thing — rehearse them hardest and slow them down.

|Beat|Tablet (cloud)|Family Hub (device)|
|---|---|---|
|1 · Cold open|★ "Ask me to plan your week"|Ambient|
|2 · The goal|★ Fuzzy one-liner|Ambient|
|3 · Cloud remembers|★ Confident plan + veto (see §11)|Ambient|
|4 · Hand-off ⟶|"Working on your Family Hub…"|★ Wakes: "Starting on your week"|
|5 · Device works|Quiet|★ Stages: check kitchen → plan → safety ✓|
|6 · Plan returns ⟵|★ Plan reveal + approval|Settles: "Plan ready"|
|7 · Approval|★ Approve → "Added"|Brief ack|
|8 · Quiet days|★ Tap Mon/Tue → view + "reminder set"|Brief confirm|
|9 · Wed adapts ⟶⟵|Tap Wed → proposal to approve|★ Lights up: "clash found: football"|
|10 · Close|★ Quantified summary|Calm|

---

## 11. Approval model — a "start → commit → adapt" ladder

Three gates, escalating in weight, each one tap:

1. **Beat 3 — start (lightest).** A **confident plan you can veto**, not a permission request — the agent _asserts_ ("Here's my plan… go ahead?" → _Go ahead / Change something_), keeping the "it knows your family" wow in the statement, not the button.
2. **Beat 7 — commit (firmer).** Adding to the shopping list changes state / costs — a firmer yes.
3. **Beat 9 — adapt.** Approving a change to the plan.

Same human-in-the-loop principle at three genuinely distinct decisions. Keep each light (one tap); let the _weight_ escalate. Avoid heavy multi-field confirmations.

---

## 12. The "wow" principle

The wow is **evidence of understanding and anticipation**, not the progress bar. Lead every screen with what the system _knew_ and what it _did for them_ ("mushroom-free for Priya," "moved Wednesday because of football"). The orchestration and harnesses earn **credibility**; the personalization earns the **wow**. Quantify the outcome at the close.

---

## 13. Open questions to decide during build

- **Audience** (leadership vs technical) — tunes the narration and whether the operator/machinery screen is foregrounded or kept as quiet backup.
- **Device planner:** LLM-backed vs rules-based for the demo.
- **Exact field sets** for the contract and result envelope (drafts above are starting points).
- **Task-manager state machine** details.
- **Materiality policy** for the change watcher (a simple rule is fine for the POC).
- **Full-week durability / reconciliation / autonomy tiers** — deferred to a later (post-POC) design, but kept in mind now.

---

_Illustrative names (Priya, Aarav) and sample dishes are placeholders for the scripted scenario — swap freely._