# UX Event Redesign — the Living Meal Plan (event-driven week)

> **SUPERSEDED (v3.2) — kept for design history.** This doc's premise — a per-goal chip
> strip (`EventStrip`) that *replaces* the sim clock, scoped to `meal_plan` — was reversed.
> v3.1 moved the world simulation to the board and v3.2 restored a **single global "Advance
> day"** on the main board (a goal-less `control` that fans out over every active goal), and
> v3.4 generalised adaptation past meals to six domains. Read `V3_DESIGN_PROPOSAL.md` §12k
> (v3.1) and §12l (v3.2) for the shipped design. The `trigger_event` mechanism described
> here still exists as the older per-goal path.

**Status:** DESIGN SPEC — ready for implementation (Codex). No code in this doc is final source; it is the precise shape to build.
**Scope:** interaction redesign only. Visual restyle (glass/gradients) is Phase 2, deferred (§8).

---

## 0. What changes, in one paragraph

The meal-plan demo stops pretending to be a clock simulation. The plan is a FIXED week
(7 dinners, Mon–Sun) that stays on screen as the hero. Below it, a strip of ~6 presenter-fired
**event chips** replaces the sim-clock controls ("Advance day" / "Set date" die for this demo).
Each chip carries a light temporal label ("Tue — groceries arrive") so the week still reads as a
narrative arc, but clicking a chip fires exactly ONE real-world event — `trigger_event` control →
cloud → device → the existing scoped-LLM adaptation path — without moving any clock. When the
approved patch comes back (`status.updated_plan` + `changed_ids`), the affected day card **morphs
in place**: old dish struck through, new dish slides in, the card pulses, the view auto-scrolls
to it, impact badges tick. A small **cloud→device handoff** animation shows the goal (and each
event) traveling from the Cloud Agent to the Device Agent.

**Honest framing:** this does NOT save tokens — each fired event still costs one scoped LLM call
on the device (user's explicit choice: LLM over hardcoding). The wins are (a) presenter control
and legibility — no "why did nothing happen on day 3?" dead clicks, no clock bookkeeping on
stage; (b) deleting the clock *as the meal-demo driver* (the SimulatedClock machinery stays for
the guest-dinner demo, untouched); (c) a visibly-alive plan.

---

## 1. Event model & trigger flow

### 1.1 Event definitions — `data/daily_events.json` (device repo)

Keep the file and its entry shape; **decouple firing from `day_offset`** and add display fields.
`day_offset` is retained but its meaning narrows to "which day of the fixed week this event
targets" — MockWorldStore still resolves it to an ISO `date` at snapshot time (anchored at plan
capture), and that resolved date is still how `AffectedPlanItems` are matched and how the LLM
knows which row to patch. It no longer controls *when* the event fires; the presenter does.

New per-event fields:

| field | type | purpose | example |
|---|---|---|---|
| `label` | string | light temporal label on the chip (narrative arc, NOT a clock) | `"Tue"` |
| `title` | string | short chip caption (≤ 4 words) | `"Groceries arrive"` |
| `order` | int | chip display order, left→right | `1` |

Existing fields (`id`, `day_offset`, `kind`, `summary`, `context`, `steer`) are unchanged.
Update the file's `comment` field to describe the new presenter-fired semantics.

**Grow the feed from 5 to 6 events** to fill the strip (user to confirm content, §9):

1. `day1-restock` — `Tue` — "Groceries arrive" (existing)
2. `day2-shortage` — `Wed` — "Paneer spoiled" (existing)
3. `day3-football` — `Thu` — "Football practice" (existing)
4. `day4-guest` — `Fri` — "Grandma joins" (existing)
5. `day5-oven` — `Sat` — "Oven unavailable" (existing)
6. **NEW** `day6-light` — `Sun` — "Lighter Sunday" — kind `preference.request`, summary
   "The family asks for a lighter, quicker Sunday dinner after a heavy week.", context
   `{ "request": "light, under 30 min" }`, steer "Swap Sunday to a light dish that cooks in
   under 30 minutes using in-stock ingredients."

### 1.2 How the UI learns the catalog — `demo_events` rides on `plan_ready`

The device ships the chip catalog to the UI inside the plan itself, so the strip appears exactly
when the plan does and the JSON file stays the single source of truth (no UI hardcoding):

- `PlanReadyPayload` gains an optional `DemoEvents` list (`demo_events` on the wire):
  `[{ "id", "label", "title", "summary", "order" }]` — display fields only, no context/steer.
- Populated in `RunCoreAsync` only when `dispatch.Domain == "meal_plan"`, read from the same
  world snapshot that is captured into `ActiveGoalContext` (`daily_events.events`, sorted by
  `order`). Absent (null) for `guest_dinner` and any other domain.
- Cloud: `handle_plan_ready` re-wraps payload via `model_dump` and every model is
  `extra="allow"` → `demo_events` passes through into `present_plan` **with zero cloud change**.

### 1.3 The new control command — `trigger_event`

Wire shape (UI → cloud → device):

```json
{ "type": "control", "goal_id": "…", "command": "trigger_event",
  "payload": { "event_id": "day3-football" } }
```

- **Device** `ControlCommands` gains `TriggerEvent = "trigger_event"`; `ControlPayload` gains
  `string? EventId`.
- **Cloud — one line, not zero.** `route_message` already forwards any UI `control` frame to the
  device, and `ControlPayload(extra="allow")` passes `event_id` through — BUT
  `Control.command` is `Literal["advance_day", "reset", "set_date"]`
  (`models/contract.py` ~line 390). An unknown command raises `ValidationError` and the frame is
  dropped (logged, connection kept). **Required change: add `"trigger_event"` to that Literal.**
  Optionally also add `event_id: str | None = None` to `ControlPayload` for self-documentation
  (not required — extras flow).
- **UI** `ControlCommand` union gains `"trigger_event"`; `ControlPayload` gains `event_id?`.

### 1.4 Device handling — `HandleControlCoreAsync` routing

New branch, checked FIRST (before any clock logic), in `GoalAgent.HandleControlCoreAsync`:

```
if command == trigger_event and payload.event_id present:
    1. resolve active goal (missing → the existing "no active goal" monitoring status,
       plus payload.event_id echoed so the chip can settle)
    2. look up the event by id in active.WorldSnapshot["daily_events"]["events"]
       (NOT a fresh feed read — the snapshot's resolved dates anchor the fixed week)
       → not found: monitoring status, material=false, note "unknown event {id}", event_id echoed
    3. build the WorldChange for exactly that entry — factor the per-entry mapping out of
       MonitorAdapt.ObserveMealChanges into a public helper (see §5, MonitorAdapt):
       Key = $"daily:{id}", Kind/Description/Context/Steer from the entry,
       AffectedPlanItems matched by the entry's resolved date against active.Plan,
       Material = _policy.IsMaterial(change)   // curated feed → true
    4. DEDUPE — same set as today: active.EmittedMaterialChanges.Add(change.Key).
       Already fired → monitoring status, material=false,
       note "event already applied", event_id echoed (chip disables). No LLM call.
    5. trace phase("adapting") → ProposeDailyAdaptationAsync(goalId, active, change)
       — the EXISTING scoped LLM → PlanPatch path, byte-for-byte. ONE LLM call.
    6. return (monitoring status with Material=true and EventId set,
               proposal with Payload.EventId set)
```

**The clock is never touched by this branch.** Ordering inside the method: the `trigger_event`
branch runs and RETURNS before the `SimulatedClock` block, so no `AdvanceDay`/`SetDate` can
occur. The trigger branch also does **not** call `_monitor.ObserveAsync` — it builds its single
change directly. Everything downstream (approval → `ApplyApprovalCoreAsync` → patch applied →
`StatusPayload.UpdatedPlan`/`ChangedIds`/`ImpactDelta`) is untouched.

**SimulatedClock disposition: keep, frozen.** It stays registered (Grounding, snapshots, and the
guest-dinner demo all read `IClock.Today`), it just never advances during the meal demo because
the UI stops sending `advance_day`/`set_date` for meal goals. `advance_day`/`set_date`/`reset`
remain valid commands (guest demo, ops). The clock-driven `ObserveMealChanges` path becomes
dormant for meal goals (offsets are all in the future relative to the frozen anchor) — leave it
in place; it shares its per-entry mapping helper with the trigger path.

### 1.5 Echoing `event_id` so chips can settle

Two optional wire fields, so the UI can map responses back to the chip that fired them:

- `StatusPayload` (device C#, TS mirror): `string? EventId` / `event_id?: string` — set on every
  status returned by the `trigger_event` branch (material, already-fired, unknown, no-goal).
- `AdaptationPayload` (device C#, TS mirror): `string? EventId` / `event_id?: string` — set when
  the proposal originates from a trigger (`ProposeDailyAdaptationAsync` gains an optional
  `eventId` parameter, passed through to the payload).

Cloud: both payload models are `extra="allow"` → passthrough, no change.

### 1.6 Sequence (one chip click)

```
UI chip click ──control:trigger_event──▶ cloud ──forward──▶ device
                                                            │ dedupe ✓, phase(adapting)
UI chip = "firing" ◀──agent_event(thinking…)── cloud ◀──────┤ ONE scoped LLM call
UI chip = "fired ✓",                                        │
AdaptationCard shows patch ◀──proposal(+event_id, patch)────┤
                            ◀──status(monitoring, +event_id)┘
user clicks Adapt ──approval──▶ cloud ──▶ device applies patch
PlanCard MORPHS ◀──status(done, updated_plan, changed_ids, impact_delta)──
```

---

## 2. The event-chip strip — `EventStrip` (new component)

**Placement:** exactly where `DemoControls` renders today — bottom of the app, below the stage
(`App.tsx` last child). **Conditional replacement, not deletion:** when the active plan carries
`demo_events`, render `EventStrip`; otherwise fall back to `DemoControls` (the guest-dinner demo
still needs its clock). `DemoControls.tsx` itself is unchanged.

The plan (the fixed week) stays the hero above; the strip reads as the presenter's "world
remote control".

### 2.1 Anatomy

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ WORLD EVENTS      ( Tue ─ Groceries arrive ✓ ) ( Wed ─ Paneer spoiled ⟳ )    │
│                   ( Thu ─ Football practice ) ( Fri ─ Grandma joins ) …      │
│                                                            [ Reset week ]    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Section eyebrow: `World events` (replaces `Sim clock`). `aria-label="World events"`.
- One chip per `demo_events` entry, sorted by `order`. Chip content: temporal label
  (`Tue`, small, `--ink-faint`) + title (`Groceries arrive`) + state glyph slot.
  Full `summary` as `title=` tooltip.
- Horizontal row, `flex-wrap: wrap` (mobile: `overflow-x: auto`, reuse the `demo-week`
  breakpoint patterns).

### 2.2 Chip states (per-chip, tracked in App state — §5 App.tsx)

| state | visual | interaction |
|---|---|---|
| `idle` | outline chip, `--stroke` border, label + title | clickable → sends `trigger_event`, → `firing` |
| `firing` | accent border + soft glow, glyph = spinner (reuse `rail-pulse` ring on a dot); title shimmer like `demo-controls--syncing` | disabled |
| `fired` | filled `--accent-soft` bg, glyph = ✓, text `--ink-dim` | permanently disabled |

Transitions: `idle →(click)→ firing →(proposal OR status with matching event_id)→ fired`.
Safety timeout: if nothing echoes back in 30 s (device offline), revert `firing → idle` so the
presenter can retry. A status with `note` containing "already applied" also lands on `fired`.
One chip firing at a time: while any chip is `firing`, the whole strip is disabled (prevents
overlapping LLM adaptations — the device dedupes per event, not per concurrent run).

Declining the adaptation still leaves the chip `fired` — the world event *happened*; declining
is a plan decision, not an event undo.

### 2.3 Reset week

A `button--ghost` at the strip's right: **Reset week**. Sends the existing `reset` control
(restores the mock world AND drops the active goal on the device) — so the UI must also reset
its stage: clear plan/chips/adaptations and return to the composer (add a `"demo_reset"` reducer
action). Guard with `window.confirm("Reset the demo? The plan and all fired events clear.")`.
This is the presenter's between-runs escape hatch, not an in-narrative control. (A softer
"replay events, keep plan" variant needs device work to restore the original plan — deferred,
§9 Q2.)

---

## 3. The morph-the-day-card animation

**Trigger:** the reducer's existing `status.updated_plan && changed_ids` branch in `App.tsx`.
Today it swaps the plan array and sets `changedPlanIds` → `plan-item--changed` flash. The morph
extends this with *before* values so the change is unmistakable.

### 3.1 State additions (App.tsx reducer)

Just before replacing `plan.payload.plan` with `updated_plan`, capture the outgoing rows:

```ts
// UiState additions
planMorphs: Record<string, { prevTitle: string; prevDetail?: string }>;  // by plan-item id
morphSeq: number;                    // bumps per adaptation → React key → restarts animations
changedImpactLabels: string[];       // labels present in status.payload.impact_delta
```

In the `status` case: for each id in `changed_ids` that exists in the CURRENT plan, record
`{prevTitle, prevDetail}` (a brand-new id — an added row — gets no morph entry and just plays
the entrance animation). Set `changedImpactLabels` from `impact_delta.map(b => b.label)`.
Increment `morphSeq`. All three reset on `goal_submitted` / `demo_reset`.

### 3.2 PlanCard rendering (the morph)

Props gain `morphs` and `morphSeq` (and keep `changedIds`). For a changed row, PlanCard renders
a stacked title block, keyed so a repeat adaptation on the same row replays:

```tsx
<li key={`${item.id}:${changed.has(item.id) ? morphSeq : 0}`}
    ref={firstChangedId === item.id ? changedRowRef : undefined}
    className={changed.has(item.id) ? "plan-item plan-item--morph" : "plan-item"} …>
  <div className="plan-item__topline">
    {morph ? <s className="plan-item__old">{morph.prevTitle}</s> : null}
    <strong className={morph ? "plan-item__title plan-item__title--in" : "plan-item__title"}>
      {item.title}
    </strong>
    <span className="plan-item__updated-badge">Updated</span> …
  </div>
  <span className={morph ? "plan-item__detail plan-item__detail--in" : "plan-item__detail"}>
    {item.detail}
  </span> …
```

The old title sits ABOVE the new one (block layout: `<s>` on its own line, small, dimmed) —
strike-through then fade-collapse; the new title slides in beneath it. No absolute positioning,
no layout thrash beyond the old line's height collapse.

### 3.3 Timeline & CSS (one choreography, ~1.9 s total, all one-shot `both`)

```
   0 ms  ─ old title visible, strike line DRAWS left→right (350 ms)
 350 ms  ─ old line holds struck (300 ms beat — the "was" registers)
 650 ms  ─ old line fades + collapses (max-height→0, opacity→0, 300 ms)
 500 ms  ─ new title+detail slide/fade IN (translateY(8px)→0, opacity 0→1, 450 ms,
           --ease-out) — overlaps the hold so the swap feels continuous
   0 ms  ─ card pulse: 2 accent glow pulses over 1.6 s (box-shadow), border → --accent
   0 ms  ─ auto-scroll (scrollIntoView, smooth, block:"center")
 ~700 ms ─ impact badges tick (see 3.4)
persist  ─ accent left edge + "Updated" badge remain (existing plan-item--changed look)
```

New CSS in `styles.css` (tokens already exist — reuse `--accent`, `--accent-glow`, `--dur*`,
`--ease-out`):

```css
/* old title: draw a strike line, hold, then collapse away */
.plan-item__old {
  display: block; font-size: 0.85em; color: var(--ink-faint);
  text-decoration: none; position: relative; overflow: hidden;
  animation: old-collapse 300ms var(--ease-out) 650ms both;
}
.plan-item__old::after {           /* the drawn strike line */
  content: ""; position: absolute; left: 0; top: 55%; height: 1.5px; width: 100%;
  background: var(--danger); transform: scaleX(0); transform-origin: left;
  animation: strike-draw 350ms var(--ease-out) both;
}
@keyframes strike-draw   { to { transform: scaleX(1); } }
@keyframes old-collapse  { to { opacity: 0; max-height: 0; margin: 0; } }
/* needs a starting max-height: */
.plan-item__old { max-height: 1.6em; }

/* new content slides in */
.plan-item__title--in, .plan-item__detail--in {
  animation: morph-in 450ms var(--ease-out) 500ms both;
}
@keyframes morph-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* the whole row pulses twice, then keeps the accent edge (existing --changed look) */
.plan-item--morph {
  border-color: var(--accent);
  box-shadow: inset 3px 0 0 0 var(--accent);
  animation: card-pulse 800ms var(--ease-out) 0ms 2 both;
}
@keyframes card-pulse {
  0%, 100% { box-shadow: inset 3px 0 0 0 var(--accent), 0 0 0 0 var(--accent-glow); }
  50%      { box-shadow: inset 3px 0 0 0 var(--accent), 0 0 24px 2px var(--accent-glow); }
}

/* impact badge tick */
.impact-badge--tick { animation: badge-tick 600ms var(--ease-spring) 700ms both; }
@keyframes badge-tick {
  0% { transform: scale(1); } 40% { transform: scale(1.12); background: var(--accent-soft); }
  100% { transform: scale(1); }
}
```

`plan-item--changed` + `plan-item-flash` are superseded by `--morph`/`card-pulse` — remove or
alias them (change-map §5).

**Auto-scroll:** `PlanCard` adds `useEffect` on `[morphSeq]`: `changedRowRef.current?.
scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" })` where
`reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches`. Only the FIRST
changed row is targeted (adaptations are single-day by design; multi-row patches scroll to the
first).

**Reduced motion:** the existing global rule (`styles.css` §motion) squashes every
animation/transition to 1 ms — the morph degrades to an instant swap with the struck old title
never lingering, plus the persistent accent edge + "Updated" badge carrying the information.
The scroll behavior switch above is the only JS-side handling needed. No per-keyframe overrides
required.

### 3.4 Impact badge tick

`PlanCard` receives `changedImpactLabels`; a badge whose `label` is in the set gets
`impact-badge--tick` (keyed with `morphSeq` to replay). The merge logic (`mergeImpact`) is
already correct — this is presentation only.

---

## 4. Cloud→device handoff visualization — `AgentHandoff` (new component)

A compact two-node graphic that makes the architecture legible in one glance: the goal lives in
the **cloud**, work happens on the **device**, and things visibly *travel* between them.

### 4.1 Anatomy & placement

Rendered by `App.tsx` directly under `ProgressRail` (its own row, ~28 px tall, right-aligned or
centered under the rail; hidden when no goal is active). `ProgressRail` itself is untouched.

```
      ☁ Cloud Agent  ────────●────────▶  ⌂ Device Agent
```

Two labeled nodes joined by a 1.5 px line (`--stroke`); a small accent comet (6 px dot with a
CSS `linear-gradient` trail) translates left→right along it when a handoff happens.

### 4.2 States & hooks (no new frames — derived entirely from existing traffic)

```ts
type HandoffState = { seq: number; kind: "goal" | "event"; phase: "traveling" | "landed" } | null;
```

Reducer/action hooks in `App.tsx`:

| moment | existing signal | AgentHandoff behavior |
|---|---|---|
| goal dispatched | `goal_submitted` action (user_goal sent) | comet travels (900 ms, `--ease-out`), then Device node shows a pulsing ring ("device working") |
| device starts | first `agent_event` of the goal (any kind) | phase → `landed`: comet done, Device node pulse continues while `working` |
| plan lands | `present_plan` | ring stops; both nodes calm |
| event fired | chip click (`trigger_event` sent) | comet travels again (`kind:"event"`, seq++ restarts the animation via key), tiny label "event" rides with it |
| adaptation arrives | `proposal` with `event_id` | phase → `landed`, Device pulse until the AdaptationCard is decided |

Implementation: `seq` as the React key on the comet span restarts the one-shot
`handoff-travel` keyframe (`transform: translateX(0) → translateX(var(--handoff-track))`,
900 ms). Device-node pulse reuses the existing `rail-pulse` keyframe. Reduced motion: global
rule collapses it to an instant state change; the Device node's static accent ring still shows
"working".

Cheap, honest, and it doubles as connection feedback (comet with nowhere to land + no
agent_event = device down — presenter sees it instantly).

---

## 5. CHANGE-MAP — exact edits per file, ordered as build phases

### Phase 1 — wire contract (device C# + cloud + TS mirrors) — small, mechanical, unblocks everything

1. **`goal-flow-device-agent-ubuntu/src/GoalFlow.Device/Contracts/Control.cs`**
   - `ControlCommands`: add `public const string TriggerEvent = "trigger_event";`
   - `ControlPayload`: add `public string? EventId { get; init; }`
   - Update the record's doc comment (event-driven demo; clock commands remain for guest demo).
2. **`…/Contracts/Status.cs`** — `StatusPayload`: add `public string? EventId { get; init; }`
   (doc: echoes the fired event so the UI chip can settle).
3. **`…/Contracts/Proposal.cs`** — `AdaptationPayload`: add `public string? EventId { get; init; }`.
4. **`…/Contracts/PlanReady.cs`** — `PlanReadyPayload`: add
   `public IReadOnlyList<DemoEvent>? DemoEvents { get; init; }`; new record
   `DemoEvent { string Id; string Label; string Title; string? Summary; int Order; }`.
5. **`goal-flow-cloud-agent/src/goalflow_cloud/models/contract.py`** — THE one-line fix:
   `command: Literal["advance_day", "reset", "set_date", "trigger_event"]` (~line 390).
   Optionally add `event_id: str | None = None` to `ControlPayload`. Nothing else — payload
   extras (`event_id`, `demo_events`, status/proposal `event_id`) all flow via `extra="allow"`.
6. **`goal-flow-agent-chat-ui/src/types/contract.ts`**
   - `ControlCommand`: add `"trigger_event"`; `ControlPayload`: add `event_id?: string`.
   - `StatusPayload`: add `event_id?: string`. `AdaptationPayload`: add `event_id?: string`.
   - New `export interface DemoEvent { id: string; label: string; title: string; summary?: string; order: number; }`
   - `PlanPayload` (or `PresentPlanPayload`): add `demo_events?: DemoEvent[]`.

### Phase 2 — device behavior (feed + trigger path)

7. **`…/data/daily_events.json`** — add `label`, `title`, `order` to all 5 events; add the 6th
   event (§1.1); rewrite the `comment` field for presenter-fired semantics.
8. **`…/Modules/Steering/MonitorAdapt.cs`**
   - Factor the per-entry body of `ObserveMealChanges` (entry → `WorldChange`, incl. the
     `AffectedPlanItems` date match and `daily:{id}` key) into
     `public WorldChange? BuildMealChange(ActiveGoalContext goal, JsonObject ev)`; the clock
     loop keeps calling it (guest demo & feed semantics unchanged).
   - Add `public WorldChange? FindMealChangeById(ActiveGoalContext goal, string eventId)` —
     scans `goal.WorldSnapshot["daily_events"]["events"]` for `id == eventId`, returns the
     built change with `Material = _policy.IsMaterial(change)`, else null.
   - Add `public static IReadOnlyList<DemoEvent> ListDemoEvents(JsonObject snapshot)` —
     maps `daily_events.events` → `DemoEvent` rows sorted by `order` (missing `order` → array
     index; missing `title` → first words of summary).
9. **`…/Agent/GoalAgent.cs`**
   - `RunCoreAsync`: after capturing the world snapshot, when `dispatch.Domain == "meal_plan"`,
     set `Payload.DemoEvents = MonitorAdapt.ListDemoEvents(snapshot)` on the `PlanReady`.
     (Note: capture the snapshot BEFORE building `ready`, or set DemoEvents from the same
     snapshot object — one snapshot, used for both.)
   - `HandleControlCoreAsync`: add the `trigger_event` branch FIRST (before the SimulatedClock
     block), per §1.4 — resolve goal → `FindMealChangeById` → dedupe on
     `EmittedMaterialChanges` → `PhaseAsync("adapting")` → `ProposeDailyAdaptationAsync(…,
     eventId)` → return `(status with EventId, proposal)`. All early-outs (no goal / unknown id /
     already fired) return a monitoring status with `EventId` echoed and `Material=false`.
     No clock mutation and no `ObserveAsync` call anywhere in this branch.
   - `ProposeDailyAdaptationAsync`: add optional `string? eventId = null` parameter; set
     `EventId = eventId` on the `AdaptationPayload`.
   - `BuildMonitoringStatus`: add optional `string? eventId = null` → `EventId` on payload.

   *Verify:* `wscat` as ui → `user_goal` (meal week) → `present_plan.payload.demo_events` has 6
   rows → send `control trigger_event day3-football` → proposal with `event_id` + patch arrives,
   sim_date unchanged → approve → `status.updated_plan`/`changed_ids` → re-send same trigger →
   "already applied" status, no LLM call.

### Phase 3 — UI event strip + state wiring

10. **`goal-flow-agent-chat-ui/src/types/ui.ts`** — add
    `export type EventChipState = "idle" | "firing" | "fired";`
    `export interface EventChip { event: DemoEvent; state: EventChipState; }`
11. **`…/src/components/EventStrip.tsx`** — NEW (§2): props
    `{ chips: EventChip[]; anyFiring: boolean; onFire: (eventId: string) => void; onResetWeek: () => void }`.
    Renders eyebrow, chip row (button per chip, disabled when not `idle` or `anyFiring`),
    Reset week ghost button with `window.confirm`.
12. **`…/src/App.tsx`**
    - `UiState` additions: `eventChips: EventChip[]` (+ the §3.1 morph fields).
    - Reducer: `present_plan` → build `eventChips` from `payload.demo_events ?? []` (all
      `idle`); new action `{ type: "event_fired"; eventId }` → chip `firing`; on inbound
      `proposal`/`status` with `payload.event_id` → that chip `fired`; `goal_submitted` clears
      chips; new action `{ type: "demo_reset" }` clears plan/chips/adaptations/ticks.
    - `sendControl` already takes a payload object — widen its payload type to
      `{ date?: string; event_id?: string }`.
    - Render: `{state.plan?.payload.demo_events?.length ? <EventStrip …/> : (state.activeGoalId ? <DemoControls …/> : null)}`
      — EventStrip's `onFire` dispatches `event_fired` + sends
      `sendControl("trigger_event", { event_id })`; `onResetWeek` sends `reset` + dispatches
      `demo_reset`. Add the 30 s `firing → idle` revert (a `useEffect` timer keyed on the firing
      chip id).
13. **`…/src/styles.css`** — event-chip classes: `.event-strip`, `.event-chip`,
    `.event-chip--firing`, `.event-chip--fired`, `.event-chip__label`, `.event-chip__glyph`
    (reuse `--accent-soft`, `rail-pulse`, the `demo-controls` responsive patterns; add the strip
    to the two `@media` blocks where `demo-controls` appears).

    *Verify:* full flow in the browser — chips appear with the plan, click → firing shimmer →
    AdaptationCard → Adapt → chip ✓; second click dead; Reset week returns to composer.

### Phase 4 — the morph animation

14. **`…/src/App.tsx`** — the §3.1 capture logic in the `status` branch (record
    `planMorphs` from the outgoing plan, `changedImpactLabels`, `morphSeq++`).
15. **`…/src/components/PlanCard.tsx`** — new props `morphs`, `morphSeq`,
    `changedImpactLabels`; stacked old/new title block (§3.2); `changedRowRef` +
    `scrollIntoView` effect on `morphSeq` (§3.3); badge tick class (§3.4).
16. **`…/src/styles.css`** — keyframes `strike-draw`, `old-collapse`, `morph-in`, `card-pulse`,
    `badge-tick` + the `.plan-item__old`, `--in`, `.plan-item--morph`, `.impact-badge--tick`
    rules (§3.3). Remove/alias `plan-item--changed` + `plan-item-flash`.

    *Verify:* fire an event, approve — the day card strikes/slides/pulses, view scrolls to it,
    badge ticks; toggle OS reduced-motion → instant swap, badge + accent edge still present.

### Phase 5 — handoff visualization

17. **`…/src/components/AgentHandoff.tsx`** — NEW (§4): props
    `{ handoff: HandoffState; working: boolean }`.
18. **`…/src/App.tsx`** — `handoff: HandoffState` in `UiState`; set on `goal_submitted` and
    `event_fired` (`traveling`, seq++); flip to `landed` on first `agent_event` /
    matching `proposal`; render `<AgentHandoff/>` under `<ProgressRail/>` when
    `activeGoalId` is set.
19. **`…/src/styles.css`** — `.agent-handoff`, node/line styles, `handoff-travel` keyframe,
    comet gradient trail; Device-node ring reuses `rail-pulse`.

Each phase is independently shippable; Phases 4 and 5 are UI-only and can land in either order.

---

## 6. What is deliberately NOT changing

- The scoped-LLM adaptation path (`ProposeDailyAdaptationAsync`, `PlanPatch`, apply-on-approval,
  `updated_plan` round-trip) — reused byte-for-byte.
- The approval/HITL flow, `AdaptationCard`, `ProposalList`, tiers.
- The guest-dinner demo: clock commands, `ObserveGuestChanges`, `DemoControls` fallback.
- Cloud routing/graph logic (beyond the one-word Literal widening).
- The `agent_event` stream, ProgressRail, PresenterFeed.

## 7. Risks / edge cases Codex must respect

- **Cloud Literal** (§1.3) — without it, `trigger_event` frames validate-fail and vanish
  silently. Do Phase 1 item 5 before testing any UI work.
- **Snapshot anchoring** — the trigger path must read events from `active.WorldSnapshot`, not a
  fresh `MockWorldStore` load, or resolved dates could re-anchor and mismatch plan rows.
- **Chip settle on decline / dead device** — chips settle on `event_id` echo, not approval;
  the 30 s revert covers a dead device.
- **`ApplyApprovalCoreAsync` returns `SimDate`** — harmless (frozen date), and `mergeDemoClock`
  ignores it visually once DemoControls is not rendered for meal goals.
- **One firing at a time** (§2.2) — the strip-level lock prevents interleaved adaptations
  clobbering each other's `_pendingPatches`/approval flow.

## 8. Phase 2 (deferred): restyle + conversation

A follow-up pass restyles the surface — real glassmorphism (backdrop blur, layered gradients),
richer plan-card art (per-dish accent hues, weekday spine down the plan), and a Family-Hub-scale
type ramp — without touching the interaction model above; the tokens block in `styles.css` is
already the single seam for it. The same pass is the natural slot for *conversational steering*:
the `GoalComposer` input can, post-plan, accept free-text nudges ("make Friday vegetarian")
that ride the same scoped-adaptation path a fired event uses — the `trigger_event` plumbing
(control → WorldChange → scoped LLM → patch → morph) is deliberately shaped so a chat-originated
steer is just an event with a user-authored `steer` string.

## 9. Open questions for the user

1. **6th event content** — is "Sun — Lighter Sunday" (preference.request) the right closer, or
   would a 7th (e.g. "Sat — price spike on salmon" budget event) be wanted? 6 chips fill the
   strip; 7 is the max before wrapping on the Hub.
2. **Reset week semantics** — full reset (world + goal, back to composer) is the cheap, honest
   option specced here. A "replay events, keep original plan" soft reset needs the device to
   keep a pristine plan copy — worth it, or is full reset fine for the demo?
3. **Chips before plan approval** — spec shows the strip as soon as `present_plan` lands (even
   before the user approves proposals). Acceptable, or should chips stay disabled until the
   first approval is sent?
