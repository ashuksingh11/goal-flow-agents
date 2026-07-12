# UX Design Spec — "Confirm understanding" gate before planning

Status: DESIGN (ready for Codex implementation) · Author: UX/flow design pass · Date: 2026-07-12
Repos touched: `goal-flow-cloud-agent` (graph, hub, contract), `goal-flow-agent-chat-ui` (types, reducer, new card, rail). Device repo: **no changes**.

---

## 1. Summary

Today the cloud graph runs `interpret_goal → load_memory → build_contract → dispatch_to_device` in one shot: the user's goal goes straight to the device planner and the first thing the user sees back is the finished plan (`present_plan`, with the "Knew" chips attached after the fact).

New flow: after the cloud has interpreted the goal and loaded memory — and **before** it builds the Task Contract or dispatches anything — it pauses and shows the user an **Understanding card**:

- the goal restated as an **objective** (from the LLM intent),
- the **hard constraints** it pulled from memory as chips (allergens, dietary, medical, budget, quiet hours — the same data that feeds the plan's "Knew" line, shown up front instead),
- a short one-line **thought** (the agent's approach),
- two actions: **"Confirm & plan"** (primary) and **"Decline"** (graceful cancel).

Only on confirm does the graph continue to `build_contract` → `dispatch_to_device`. The run now has **two** `interrupt()` pauses: the new understanding-confirm gate, then the existing plan-approval gate (`hitl_approval`), which is untouched. Applies to **all domains** (meal_plan, guest_dinner, future). Constraints are display-only at this gate (not editable).

```
user goal
  → interpret_goal (LLM)                    [cloud]
  → load_memory                             [cloud]
  → present_understanding  ── interrupt() ──→ UI: `understanding` frame  ← NEW
        │  user "Confirm & plan" → resume {confirmed:true}
        │  user "Decline"        → resume {confirmed:false} → goal_declined → END
  → build_contract → dispatch_to_device     [cloud → device]
  → collect_plan   ── interrupt() ──  (await plan_ready, existing)
  → hitl_approval  ── interrupt() ──  (present_plan approval, existing, UNCHANGED)
  → relay_decisions → monitor → finalize
```

---

## 2. Grounding — how it works today (what we build on)

Everything below was verified against the current code; file paths are the anchor points for the change-map in §7.

### 2.1 Cloud graph (`goal-flow-cloud-agent/src/goalflow_cloud/graph/nodes.py`)

- `GraphState` (TypedDict, `total=False`) is checkpointed per goal, `thread_id = goal_id` (MemorySaver).
- `interpret_goal` → LLM structured output `{domain, objective, success_criteria, scope, time_window}` into `state["intent"]`; on failure sets `state["error"]` and `route_after_interpret` sends it to `explain_block` (this error path **bypasses** the new gate — nothing to confirm).
- `load_memory` → `state["memory"] = {family_id, hard: hard_safety_block(profile), bias: soft_bias_block(profile)}`. `memory["hard"]` is exactly the data the plan's "Knew" line surfaces later (via `server.build_knew` reading the dispatched contract's `constraints.hard`).
- `build_contract` mints `correlation_id` (and `goal_id` fallback), assembles + validates `Dispatch`, stores `state["contract"]`.
- Interrupt pattern (the model for the new node): `hitl_approval` calls `interrupt({...kind, goal_id, ...payload})`; the value returned by `interrupt()` on resume is whatever the hub passed to `Command(resume=...)`; the node defensively unwraps `{"payload": {...}}` shapes.
- Edges are wired in `build_graph()`; today `graph.add_edge("load_memory", "build_contract")` is the seam we cut.
- Hub entry points: `start_goal(graph, goal_text, goal_id)` invokes and **currently raises if `state["contract"]` is missing** after the first pause — that assumption breaks with the new earlier pause and must change (§4.1). `resume_goal(graph, goal_id, resume_value)` wraps `Command(resume=...)`.

### 2.2 WS hub (`goal-flow-cloud-agent/src/goalflow_cloud/server.py`)

- `handle_user_goal`: mints `goal_id`, runs `start_goal` in a thread, then — today — reads `state["contract"]`, caches it in `dispatched_contracts[goal_id]`, and `registry.send_to("device", frame)`. With the new gate, the first pause happens **before** the contract exists, so the dispatch step moves into the confirm handler (§4.2).
- `handle_approval` is the resume model: `resume_goal(graph, approval.goal_id, decisions)` then forward to device.
- `handle_plan_ready` re-wraps `plan_ready` as `present_plan` and injects `payload["knew"] = build_knew(dispatched_contracts[goal_id])`. `build_knew` flattens `constraints.hard` (allergens/dietary/medical/budget/quiet hours) + soft + context into display-ready `{label: str | list[str]}` chips — the understanding card reuses the **hard** part of exactly this logic (§4.2, `_hard_knew`).
- UI frames are broadcast via `registry.send_to("ui", frame)`.

### 2.3 Contract models (`goal-flow-cloud-agent/src/goalflow_cloud/models/contract.py`)

All models extend `_ContractModel` (`extra="allow"`), discriminated on `type`. New frames slot in beside `PresentPlan`/`Approval` and join the `ContractMessage` union. **No `TaskStatus` enum bump is needed** — the understanding frame ships with `task_status: "grounding"` (already valid), keeping all three mirrors (py/ts/C#) compatible; the device never sees the new frames at all.

### 2.4 UI (`goal-flow-agent-chat-ui/src`)

- `lib/ws.ts` has an **`INBOUND_TYPES` allowlist** (`hello_ack, capabilities, agent_event, present_plan, proposal, status`) — a new inbound type is *silently dropped* unless added there. Easy to miss; called out in the change-map.
- `App.tsx`: one pure reducer (`reduceInbound`) maps inbound frames → `UiState`. `goal_submitted` sets `phase:"interpreting", working:true`; `working && !plan` drives the skeleton; `present_plan` sets the plan hero and `working:false`. Outbound: `submitGoal`, `sendDecisions` (approval), `sendControl`.
- `components/PlanCard.tsx` renders `payload.knew` as `.knew-chip` spans with a `knewValue()` guard (primitives/string-lists only) — the UnderstandingCard reuses this exact visual + guard.
- `types/ui.ts` `RAIL_PHASES` = Interpreting → Grounding → Planning → Checking → Approval → Monitoring; `maxRailPhase` keeps the rail monotonic (index-based on the array). `ProgressRail.tsx` renders purely from `RAIL_PHASES` — inserting a step needs **no ProgressRail code change**.

---

## 3. The graph change (cloud)

### 3.1 New node `present_understanding` (after `load_memory`, before `build_contract`)

```python
def present_understanding(state: GraphState) -> GraphState:
    """Confirm-understanding gate (HITL #1): show the interpreted objective +
    hard constraints + a one-line approach, and pause until the user confirms.
    Nothing is dispatched to the device until this returns confirmed=True."""
    intent = state["intent"]
    memory = state["memory"]
    domain = _canonical_domain(intent["domain"], state.get("goal_text", ""), intent["objective"])
    understanding = {
        "objective": intent["objective"],
        "domain": domain,
        "time_window": intent.get("time_window", {}),
        "hard": memory.get("hard", {}),          # raw DATA; the hub flattens to chips
        "thought": _understanding_thought(intent, memory.get("hard", {}), domain),
    }
    incoming = interrupt(
        {
            "kind": "understanding_confirmation",
            "goal_id": state.get("goal_id"),
            "understanding": understanding,
        }
    )
    # Defensive unwrap, same style as hitl_approval:
    if isinstance(incoming, dict) and "payload" in incoming:
        incoming = incoming["payload"]
    confirmed = bool(isinstance(incoming, dict) and incoming.get("confirmed"))
    return {
        "understanding": understanding,
        "understanding_confirmed": confirmed,
        "task_status": "grounding",
        "event_log": [_event(state, "understanding_confirmed" if confirmed else "understanding_declined", {})],
    }
```

`GraphState` gains two keys: `understanding: dict[str, Any]` and `understanding_confirmed: bool`.

Notes:
- `goal_id` already exists here (passed into the initial invoke by `handle_user_goal`); `correlation_id` does **not** yet (minted in `build_contract`) — the understanding frame therefore omits it (optional field).
- The interrupt payload carries the full understanding (the node's return value only lands in state *after* resume, so the hub must read the interrupt value, not state — see §4.1).
- The hard constraints ride as **raw data** (`memory["hard"]`, same block that later becomes `contract.constraints.hard`); chip-flattening stays in one place in the hub (§4.2).

### 3.2 The one-line "thought" — recommendation: deterministic template

Recommended (cheapest, zero latency, zero OpenRouter spend — relevant given the low-credit-key comment in `interpret_goal`): a template built from data the node already has.

```python
def _understanding_thought(intent: dict, hard: dict, domain: str) -> str:
    tw = intent.get("time_window", {})
    n = sum(1 for k in ("allergens", "medical", "dietary") for _ in (hard.get(k) or [])) \
        + (1 if hard.get("budget_cap") else 0) + (1 if hard.get("quiet_hours") else 0)
    label = domain.replace("_", " ")
    window = f"{tw.get('start', '')} → {tw.get('end', '')}".strip(" →")
    guard = f", honoring {n} household constraint{'s' if n != 1 else ''}" if n else ""
    return f"I'll shape a {label} for {window}{guard}, then have your Family Hub build the step-by-step plan."
```

Reads like: *"I'll shape a meal plan for 2026-07-12 → 2026-07-18, honoring 5 household constraints, then have your Family Hub build the step-by-step plan."* Alternative (only if the template feels flat in demos): a tiny `ChatOpenAI` one-liner call with `max_tokens≈60`, falling back to the template on any exception — do **not** let a thought failure kill the run. Ship the template first; the LLM line is a follow-up toggle. (Open question §8.)

### 3.3 New terminal node `goal_declined` + router + edges

```python
def goal_declined(state: GraphState) -> GraphState:
    """User declined the understanding — end the run gracefully. No contract,
    no dispatch, nothing reached the device."""
    return {
        "task_status": "done",
        "explanation": {"type": "declined", "message": "Goal cancelled before planning."},
        "event_log": [_event(state, "goal_declined", {})],
    }

def route_after_understanding(state: GraphState) -> str:
    return "build_contract" if state.get("understanding_confirmed") else "goal_declined"
```

Wiring in `build_graph()` — the only edge changes:

```python
graph.add_node("present_understanding", present_understanding)
graph.add_node("goal_declined", goal_declined)

# REPLACE: graph.add_edge("load_memory", "build_contract")
graph.add_edge("load_memory", "present_understanding")
graph.add_conditional_edges(
    "present_understanding",
    route_after_understanding,
    {"build_contract": "build_contract", "goal_declined": "goal_declined"},
)
graph.add_edge("goal_declined", END)
```

Everything downstream (`build_contract → dispatch_to_device → collect_plan → route_on_safety → hitl_approval → ...`) is untouched — the run now simply contains **two interrupts** (three counting the internal `await_plan_ready` / `monitor` waits): understanding-confirm, then plan-approve. The `interpret_goal` error path still routes straight to `explain_block` and never shows the gate.

### 3.4 `start_goal` / `resume_goal` — surface the interrupt value

`start_goal` currently raises when `state["contract"]` is missing after the first invoke; with the gate, the first pause is *before* the contract. Change both entry points to return the paused interrupt value alongside state (LangGraph puts pending interrupts on the invoke result under `"__interrupt__"` as `Interrupt` objects; `graph.get_state(config).tasks[*].interrupts` is the fallback source):

```python
def _with_interrupt(result: dict, state: dict) -> dict[str, Any]:
    out = dict(state)
    interrupts = result.get("__interrupt__") or []
    out["_interrupt"] = interrupts[0].value if interrupts else None
    return out

def start_goal(graph, goal_text, goal_id):
    config = {"configurable": {"thread_id": goal_id}}
    result = graph.invoke({...as today...}, config=config)
    return _with_interrupt(result, graph.get_state(config).values)   # no "contract" assertion anymore

def resume_goal(graph, goal_id, resume_value):
    config = {"configurable": {"thread_id": goal_id}}
    result = graph.invoke(Command(resume=resume_value), config=config)
    return _with_interrupt(result, graph.get_state(config).values)
```

`_interrupt` is a hub-facing convenience key (underscore = not graph state); existing callers ignore it.

---

## 4. The frames (contract + hub mapping)

### 4.1 New frames — CONTRACT v2.1

Two frames, UI↔cloud only (the device never sees them). Python in `models/contract.py`, TS mirror in `types/contract.ts`, prose in cloud repo `/CONTRACT.md`.

**`understanding` (cloud → ui)** — emitted when the graph pauses at `present_understanding`:

```jsonc
{
  "type": "understanding",
  "goal_id": "…",
  "task_status": "grounding",              // existing enum value — no TaskStatus bump
  "payload": {
    "objective": "Plan dinners for this week for the family",
    "domain": "meal_plan",
    "knew": {                               // SAME shape as present_plan payload.knew,
      "allergens": ["peanuts"],             // hard-constraints subset only
      "dietary": ["vegetarian (Mom)"],
      "medical": ["low-sodium (Dad)"],
      "budget": "$120",
      "quiet hours": "{'start': '21:30', 'end': '07:00'}"
    },
    "thought": "I'll shape a meal plan for 2026-07-12 → 2026-07-18, honoring 5 household constraints, then have your Family Hub build the step-by-step plan.",
    "time_window": { "start": "2026-07-12", "end": "2026-07-18" }
  }
}
```

**`understanding_response` (ui → cloud)** — the confirm/decline. A small dedicated frame, **not** the `approval` channel: `handle_approval` resumes with a decisions list *and forwards to the device* — both wrong here (nothing is on the device yet), and overloading it would force fake `proposal_id`s. Control frames are device-bound clock commands — also wrong.

```jsonc
{ "type": "understanding_response", "goal_id": "…", "payload": { "confirmed": true } }
```

Pydantic (in `models/contract.py`, beside PresentPlan/Approval; both added to `ContractMessage`):

```python
class UnderstandingPayload(_ContractModel):
    objective: str
    domain: str = ""
    knew: dict[str, Any] = Field(default_factory=dict)   # display-ready chips (see PlanPayload.knew)
    thought: str = ""
    time_window: dict[str, str] | None = None

class Understanding(_ContractModel):
    type: Literal["understanding"] = "understanding"
    goal_id: str
    correlation_id: str | None = None      # not yet minted at this stage
    task_status: TaskStatus = "grounding"
    payload: UnderstandingPayload

class UnderstandingResponsePayload(_ContractModel):
    confirmed: bool

class UnderstandingResponse(_ContractModel):
    type: Literal["understanding_response"] = "understanding_response"
    goal_id: str
    payload: UnderstandingResponsePayload
```

### 4.2 Hub mapping (server.py)

**Interrupt → `understanding` frame.** `handle_user_goal` changes from "read contract, dispatch" to "inspect where the run paused":

```python
async def handle_user_goal(user_goal: UserGoal) -> None:
    goal_id = str(uuid4())
    state = await asyncio.to_thread(graph_nodes.start_goal, graph, user_goal.text, goal_id)
    if state.get("error"):
        ...existing status(done, note=error) branch, unchanged...
        return
    itr = state.get("_interrupt")
    if isinstance(itr, dict) and itr.get("kind") == "understanding_confirmation":
        u = itr.get("understanding", {})
        frame = Understanding(
            goal_id=goal_id,
            payload=UnderstandingPayload(
                objective=u.get("objective", ""),
                domain=u.get("domain", ""),
                knew=_hard_knew(u.get("hard") or {}),   # flatten to chips HERE (one place)
                thought=u.get("thought", ""),
                time_window=u.get("time_window"),
            ),
        )
        logger.info("task_status status=grounding gate=understanding")
        await registry.send_to("ui", frame.model_dump(mode="json", exclude_none=True))
        return
    # Defensive fallback (should not happen once the gate is unconditional):
    if state.get("contract"):
        ...existing dispatch path...
```

`_hard_knew(hard)` is **extracted from the existing `build_knew`** (the allergens/dietary/medical/`budget_cap→"budget"`/`quiet_hours→"quiet hours"` block, including the flat-values-only `add()` guard); `build_knew` then calls `_hard_knew(hard)` and appends its soft/context chips. One flattening implementation, two consumers — the understanding card and the plan's Knew line stay visually identical by construction.

**`understanding_response` → resume.** New route in `route_message` (`sender_role == "ui" and frame_type == "understanding_response"`) → new handler:

```python
async def handle_understanding_response(response: UnderstandingResponse) -> None:
    confirmed = response.payload.confirmed
    state = await asyncio.to_thread(
        graph_nodes.resume_goal, graph, response.goal_id, {"confirmed": confirmed}
    )
    if not confirmed:
        # Graph ran goal_declined -> END. Broadcast a terminal status for
        # observability (presenter feed, second dashboards); the initiating UI
        # already reset locally and drops frames for the declined goal (§5.3).
        await registry.send_to("ui", {
            "type": "status", "goal_id": response.goal_id,
            "correlation_id": state.get("correlation_id") or "-",
            "task_status": "done",
            "payload": {"material": False, "executed": [], "note": "Goal cancelled before planning."},
        })
        return
    contract = state.get("contract")
    if not contract:            # build_contract validation error after confirm
        await registry.send_to("ui", { ...status(done, note=state.get("error", "dispatch build failed"))... })
        return
    dispatched_contracts[response.goal_id] = contract      # moved here from handle_user_goal
    logger.info("task_status status=planning")
    await registry.send_to("device", contract)             # run is now paused at collect_plan, as before
```

After confirm, the run has advanced through `build_contract → dispatch_to_device` and is parked at `collect_plan`'s `await_plan_ready` interrupt — exactly the state the pre-change `handle_user_goal` left it in, so `handle_plan_ready`, `handle_approval`, monitoring, adaptation and `build_knew` for `present_plan` all work **unchanged**.

Resilience note: `dispatched_contracts`/`seen_correlation_ids` behavior is unchanged; a UI reload while paused at the gate loses the card (no replay cache) — acceptable for the demo, flagged in §8.

---

## 5. The UI

### 5.1 `UnderstandingCard` (new: `src/components/UnderstandingCard.tsx`)

The stage hero while the gate is open — same card language as `PlanCard` (`plan-card`-style container, `card-enter` animation, `.eyebrow` + `.knew-chip` vocabulary).

Anatomy, top to bottom:

1. **Eyebrow**: `Understood` (mirrors PlanCard's `Knew` eyebrow styling).
2. **Objective**: `payload.objective` as the card heading (`<h2 class="understanding-card__objective">`). Optional sub-line: humanized `time_window` ("Sat, Jul 12 – Fri, Jul 18", `Intl.DateTimeFormat`, same approach as PlanCard's `formatWhen`).
3. **Constraint chips**: `payload.knew` rendered exactly like PlanCard's Knew line — same `.knew-chip` class, same `knewValue()` defensive guard (extract `knewValue` + a small `KnewChips` helper into a shared spot, or copy the 6-line function; see change-map). Empty `knew` → render a single muted chip "no stored constraints" rather than nothing (the gate must still read as informed).
4. **Thought**: one italic line, `payload.thought`, prefixed with a subtle label — `<p class="understanding-card__thought"><span class="eyebrow">Approach</span> {thought}</p>`.
5. **Actions** (`.understanding-card__actions`): primary button **"Confirm & plan"** (reuse the heavy/primary approval button styling from ProposalList's firm tier) and ghost/secondary **"Decline"**. Buttons disable immediately on click (single-shot).

Resolved-confirmed state: after confirm the card collapses to a slim strip — `✓ Understanding confirmed — planning on your Family Hub…` — above the AgentStream/skeleton, and disappears entirely when `present_plan` lands (the plan's own Knew line takes over the constraint display). Declined: the card unmounts (state reset, §5.3).

```tsx
export interface UnderstandingCardProps {
  understanding: Understanding;
  /** true once "Confirm & plan" was clicked (renders the compact strip). */
  resolved: boolean;
  onRespond: (confirmed: boolean) => void;
}
```

### 5.2 Types

`types/contract.ts`: add `UnderstandingPayload`, `Understanding`, `UnderstandingResponse` interfaces mirroring §4.1 (knew reuses `PlanKnew`); add `Understanding` to `UiInboundMessage` + `ContractMessage`, `UnderstandingResponse` to `UiOutboundMessage` + `ContractMessage`.

`lib/ws.ts`: add `"understanding"` to `INBOUND_TYPES` — **without this the frame is silently dropped** (`isUiInboundMessage` allowlist).

### 5.3 Reducer + state (`App.tsx`)

New `UiState` fields (+ `INITIAL_STATE` defaults):

```ts
understanding: Understanding | null;   // null
understandingResolved: boolean;        // false — true once Confirm was clicked
declinedGoalId: string | null;         // null — drop stray frames for a declined goal
```

New action: `{ type: "understanding_response_sent"; confirmed: boolean }`.

Reducer changes:

- **Top of `reduceInbound`**: `if ("goal_id" in message && message.goal_id === state.declinedGoalId) return state;` — the cloud's post-decline `status(done)` echo (and any stragglers) must not resurrect the goal or shove the rail to Monitoring.
- **`case "understanding"`**: `{ ...withGoal, understanding: message, understandingResolved: false, working: false, phase: maxRailPhase(withGoal.phase, "confirming") }`. `working:false` parks the caret/skeleton — the stage is waiting on the *user*, not the agent; `planPending` (`working && !plan`) correctly hides the skeleton while the card is up.
- **`case "understanding_response_sent"`** (in the outer `reducer`):
  - confirmed: `{ ...state, understandingResolved: true, working: true, handoffSeq: state.handoffSeq + 1, phase: maxRailPhase(state.phase, "planning") }` — skeleton returns, the `AgentHandoff` cloud→device animation replays (the dispatch really is crossing to the device now), rail advances; the device's own `agent_event` phases take over from there.
  - declined: reset the stage to idle — `{ ...state, understanding: null, understandingResolved: false, declinedGoalId: state.activeGoalId, activeGoalId: null, phase: null, working: false, agentEntries: [], draftItems: [], transcript: [...state.transcript, { kind: "note", id: state.nextId, text: "Goal cancelled — nothing was planned." }], nextId: state.nextId + 1 }`. Composer is front-and-center again; `frames`/`modules`/`demoClock` are kept.
- **`case "goal_submitted"`**: add `understanding: null, understandingResolved: false, declinedGoalId: null` to the existing reset block.
- **`case "present_plan"`**: add `understanding: null, understandingResolved: false` (plan card takes over; its Knew line re-shows constraints, now with soft prefs too).

App component — one new sender + render slot:

```tsx
const respondUnderstanding = (confirmed: boolean) => {
  const u = state.understanding;
  if (!u) return;
  dispatch({ type: "understanding_response_sent", confirmed });
  socketRef.current?.send({ type: "understanding_response", goal_id: u.goal_id, payload: { confirmed } });
};
```

Render, inside `stage__main`, after the `AgentStream` block and **before** the `planPending` skeleton block:

```tsx
{state.understanding && !state.plan ? (
  <UnderstandingCard
    understanding={state.understanding}
    resolved={state.understandingResolved}
    onRespond={respondUnderstanding}
  />
) : null}
```

`PresenterFeed` gets both new frames for free (it renders `state.frames`, which `recv`/`sent` already populate).

### 5.4 Progress rail — new "Confirm" step between Grounding and Planning

Decision: **insert a dedicated step** rather than reuse "Approval". Reusing Approval is not viable: `maxRailPhase` keeps the rail monotonic, so lighting Approval (index 4) at the gate would make it impossible to ever show Planning/Checking (indices 2–3) afterwards — the rail would be permanently wrong. `RailPhase` is UI-side vocabulary (`types/ui.ts`, explicitly *not* wire contract), so this costs no protocol change.

`types/ui.ts`:

```ts
export type RailPhase =
  | "interpreting" | "grounding" | "confirming"      // ← new, between grounding & planning
  | "planning" | "checking" | "awaiting_approval" | "monitoring";

export const RAIL_PHASES = [
  { id: "interpreting", label: "Interpreting" },
  { id: "grounding", label: "Grounding" },
  { id: "confirming", label: "Confirm" },            // ← new (7 steps total)
  { id: "planning", label: "Planning" },
  { id: "checking", label: "Checking" },
  { id: "awaiting_approval", label: "Approval" },
  { id: "monitoring", label: "Monitoring" },
] as const;
```

- `railPhaseFromStatus` / `railPhaseFromAgentPhase`: **no change** — no wire status maps to `confirming`; the reducer sets it explicitly on the `understanding` frame. (Both switches are exhaustive over their inputs and unaffected.)
- `maxRailPhase`, `ProgressRail.tsx`, `stepState`: no code change — all index-driven off `RAIL_PHASES`.
- Visual: the gate reads as *Interpreting ✓ → Grounding ✓ → **Confirm** (pulsing) → …*; on confirm the reducer jumps to `planning` and Confirm gets its check. Two user gates on the rail ("Confirm" early, "Approval" late) is the honest story of the two interrupts.
- `styles.css`: verify the rail fits 7 steps at demo width (labels are short; if tight, reduce `.rail-label` min-width / gap).

### 5.5 Styles (`styles.css`)

New classes, all composed from existing vocabulary: `.understanding-card` (base = plan-card panel + `card-enter`), `.understanding-card__objective`, `.understanding-card__thought` (muted italic), `.understanding-card__actions` (flex row, gap; primary = existing approve-button style, secondary = ghost), `.understanding-card--resolved` (compact strip variant, single line, success tint).

---

## 6. Flow walkthroughs (acceptance)

**Confirm path (happy):** submit goal → rail Interpreting (local) → cloud interprets + loads memory → UI receives `understanding` → card animates in, rail pulses **Confirm**, no skeleton → user clicks *Confirm & plan* → card collapses to ✓ strip, handoff animation fires, skeleton + rail Planning → device streams `agent_event`s → `present_plan` (with full Knew incl. soft prefs) → existing approval flow → monitoring. Both interrupts hit in one run; `hitl_approval` behavior byte-identical to today.

**Decline path:** …card shown → user clicks *Decline* → UI resets to composer with transcript note "Goal cancelled — nothing was planned."; cloud resumes graph → `goal_declined` → END (no contract, **nothing sent to the device**); cloud broadcasts `status(done, note)` which the initiating UI drops via `declinedGoalId` (other dashboards/presenter feeds see it). A fresh goal submits cleanly afterwards (new `goal_id` = new thread).

**Error path:** interpret failure → `explain_block` (no gate shown) → existing `status(done, note=error)` — unchanged. `build_contract` validation failure *after* confirm → hub sends `status(done, note)` (§4.2).

**Both domains:** gate is unconditional in the graph — meal_plan and guest_dinner (and any future domain) pass through identically; nothing in the new node/frames is domain-specific.

---

## 7. CHANGE-MAP — phased for Codex

Order matters: contract types first (both sides), then graph, then hub, then UI. Each phase leaves the system runnable.

### Phase 1 — Contract frames (cloud + UI mirrors) · no behavior change
| File | Change |
|---|---|
| `goal-flow-cloud-agent/src/goalflow_cloud/models/contract.py` | Add `UnderstandingPayload`, `Understanding`, `UnderstandingResponsePayload`, `UnderstandingResponse` (§4.1); add both to `ContractMessage` union. |
| `goal-flow-cloud-agent/CONTRACT.md` | Document the two frames + the new gate in the flow narrative (v2.1). |
| `goal-flow-agent-chat-ui/src/types/contract.ts` | Mirror the two frames; extend `UiInboundMessage` (`Understanding`), `UiOutboundMessage` (`UnderstandingResponse`), `ContractMessage`. |
| `goal-flow-agent-chat-ui/src/lib/ws.ts` | Add `"understanding"` to `INBOUND_TYPES` (frame is silently dropped otherwise). |

Verify: `python -c "from goalflow_cloud.models.contract import Understanding, UnderstandingResponse"`; `npx tsc --noEmit` in the UI repo.

### Phase 2 — Graph gate (cloud) · cloud pauses, hub not yet wired
| File | Change |
|---|---|
| `goal-flow-cloud-agent/src/goalflow_cloud/graph/nodes.py` | `GraphState` += `understanding`, `understanding_confirmed`. Add `_understanding_thought()` (template, §3.2), `present_understanding` node (§3.1), `goal_declined` node + `route_after_understanding` (§3.3). Rewire edges: `load_memory → present_understanding` (replacing `load_memory → build_contract`), conditional to `build_contract`/`goal_declined`, `goal_declined → END`. Update `start_goal`/`resume_goal` to return `_interrupt` and drop the missing-contract raise (§3.4); update the module docstring pipeline diagram. |

Verify (scriptable, no device needed): drive `build_graph()` directly — invoke with a goal, assert the run pauses with interrupt kind `understanding_confirmation` and `state["contract"]` is absent; resume `{"confirmed": False}` → state has `explanation.type == "declined"`, `task_status == "done"`; fresh thread + resume `{"confirmed": True}` → run proceeds and pauses at `await_plan_ready` with `state["contract"]` present.

### Phase 3 — Hub wiring (cloud) · end-to-end over WS
| File | Change |
|---|---|
| `goal-flow-cloud-agent/src/goalflow_cloud/server.py` | Import new models. Extract `_hard_knew(hard)` from `build_knew` (which now calls it). Rewrite `handle_user_goal` tail: on `_interrupt.kind == "understanding_confirmation"` build + send the `understanding` frame to ui, do **not** dispatch (§4.2). Add `understanding_response` route in `route_message` + `handle_understanding_response` (resume; on confirm cache `dispatched_contracts` + dispatch to device; on decline / missing contract send terminal `status`) (§4.2). Update module docstring routing table. |

Verify: run cloud + device; with a WS probe as "ui": send `user_goal` → expect `understanding` frame (objective/knew/thought populated); send `understanding_response{confirmed:true}` → device receives `dispatch`, then `present_plan` arrives with an *identical-shape* `knew` superset; separately decline → expect `status(done, "Goal cancelled…")` and **no** device frame. Repeat for a guest_dinner goal.

### Phase 4 — UI
| File | Change |
|---|---|
| `goal-flow-agent-chat-ui/src/types/ui.ts` | `RailPhase` += `"confirming"`; insert `{ id: "confirming", label: "Confirm" }` into `RAIL_PHASES` after grounding (§5.4). |
| `goal-flow-agent-chat-ui/src/components/UnderstandingCard.tsx` | **New** component (§5.1): objective, `KnewChips` (reuse/lift `knewValue` guard from PlanCard), thought line, Confirm & plan / Decline, resolved-strip variant. |
| `goal-flow-agent-chat-ui/src/App.tsx` | `UiState` += `understanding`/`understandingResolved`/`declinedGoalId` (+ INITIAL_STATE). New action `understanding_response_sent`. Reducer: declined-goal drop guard, `case "understanding"`, resets in `goal_submitted`/`present_plan`, response handling (§5.3). `respondUnderstanding` sender; render card between AgentStream and skeleton. |
| `goal-flow-agent-chat-ui/src/styles.css` | `.understanding-card*` styles (§5.5); check rail at 7 steps. |
| `goal-flow-agent-chat-ui/src/components/ProgressRail.tsx` | Expected **no change** (renders from `RAIL_PHASES`); visual QA only. |

Verify in browser (full stack): happy path (card → confirm → skeleton → plan → approve → monitor; rail hits all 7 steps in order, never regresses); decline path (reset to composer + note, no device activity, next goal works); presenter feed shows `understanding` + `understanding_response`; two UI tabs both render the card and either can confirm (second tab's confirm resumes an already-resumed thread — see §8 risk).

### Phase 5 — Docs & demo polish
| File | Change |
|---|---|
| `goal-flow-agents/docs/DEMO_RUNBOOK.md` / `FINAL_DEMO.md` | Add the confirm beat to the demo script (it's a strong "human in command" moment before any device work). |
| `goal-flow-cloud-agent/docs/ARCHITECTURE.md` + `diagrams.md` | Update pipeline + Mermaid: two HITL interrupts. |

---

## 8. Risks & open questions (confirm before/while building)

1. **Thought source** — spec recommends the deterministic template (§3.2): zero cost/latency, never fails, reads fine for the demo. Confirm; the tiny-LLM one-liner (with template fallback) can be a config-flagged follow-up if demos want more personality.
2. **Decline semantics** — designed as a *full local reset* to the composer (goal dead, new `goal_id` on next submit), with the cloud echoing a terminal `status` that the initiating UI drops. Alternative (keep the declined card visible in a "cancelled" state for narrative) is a pure UnderstandingCard-variant change if wanted.
3. **Rail wording** — "Confirm" chosen for the new step (vs "Align", "Review"); 7 steps must fit the demo viewport — check `styles.css` at target resolution.
4. **Double-confirm race (multi-UI)** — with two dashboards, both get the card; the second `understanding_response` resumes a thread that is no longer paused at that interrupt. LangGraph will raise / mis-resume. Mitigation options: (a) hub tracks goals past the gate (e.g. `goal_id in dispatched_contracts` or a small `resolved_understandings: set`) and drops duplicates — recommended, ~4 lines in `handle_understanding_response`; (b) accept for the single-presenter demo. Decide at Phase 3.
5. **UI reload while gated** — the hub doesn't replay the `understanding` frame to late-joining UIs (unlike cached `capabilities`); a mid-gate reload orphans the run until the goal is resubmitted. Acceptable for demo; a `pending_understandings: dict[goal_id, frame]` replay-on-register cache is the fix if needed.
6. **`__interrupt__` surface** — §3.4 assumes the installed LangGraph returns pending interrupts on `invoke()` under `"__interrupt__"`; if the pinned version predates that, read `graph.get_state(config).tasks[0].interrupts[0].value` instead (both noted in the code comment). Verify in Phase 2's script first.
7. **Latency at the gate** — the card appears only after the interpret LLM call (~seconds). The existing `goal_submitted → working:true` AgentStream/caret covers the wait; no new spinner needed. Confirm the "Interpreting → card" beat feels right in rehearsal.
