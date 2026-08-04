# GoalFlow — Design

**The one design document.** It describes the system as it is today, not how it got here.
There are no per-version design docs and no per-milestone plans — §10 carries the version
history in a few lines each, and that is the whole record. When behaviour changes, this file
changes with it.

The only other document in this folder is **[FINAL_DEMO.md](FINAL_DEMO.md)** — how to run it.
Run commands live *there*, in one place, so they cannot drift.

---

## 1. What GoalFlow is

A proof-of-concept **goal-based agent** for the Samsung Tizen Family Hub. The user states an
outcome, not a command — *"plan our dinners this week, healthy and using up what's in the
fridge"* — and a **cloud agent** and an **on-device agent** turn it into a grounded,
approval-gated plan that keeps adapting as the world moves.

Two claims the whole architecture exists to support:

> **"LLM plans, code checks."** The model proposes; deterministic code decides what may
> happen. The thing the code checks is `constraints.hard` (§5), and no model output ever
> reaches it.

> **"Fake the world; make the mechanism real."** The fridge, the calendar, prices and "the
> week" are mocked. The orchestration — two tiers, a versioned contract, grounding, the
> human gates, live adaptation — is real.

**Two tiers, and why the split falls where it does.** The cloud owns the *goal*: interpreting
it, household policy, the human, and board aggregation. The device owns the *plan*:
decompose, ground, check, execute, monitor. The cloud deliberately sends **no task list** — a
cloud-authored plan is an ungrounded guess (it cannot know the thermostat is offline or that
the paneer expires Thursday), two planners means two sources of truth, and it would kill the
live grounding stream that is the demo's best moment.

---

## 2. The pieces

| Repo | What it is | Stack |
|---|---|---|
| `goal-flow-agents` | docs only — this file and the demo run-sheet | — |
| `goal-flow-cloud-agent` | the WebSocket hub + LangGraph goal graph; owns the contract | Python, FastAPI, LangGraph |
| `goal-flow-device-agent-ubuntu` | the device agent and its harness — the dev surface | .NET 8, Semantic Kernel |
| `goal-flow-device-agent-tizen` | the same agent as a Tizen service; core is copied, host differs | .NET 8, Tizen |
| `goal-flow-agent-chat-ui` | the create-phase surface — "watch it think", the plan, approvals | React 18, Vite, TS |
| `goal-flow-agent-board-ui` | **home** — the Agent Board over every running goal | React 18, Vite, TS |
| `goal-flow-agent-bixby-ui` | dev surrogate for Bixby: where the user actually types | React 18, Vite, TS |
| `goal-flow-agent-tizen-ui` | NUI progress mirror on the fridge panel; **parked at v4** | .NET 8, Tizen NUI |

**Everything goes through the hub.** No UI ever talks to the device and no surface talks to
another; the cloud is the only router. That single invariant is what makes the board a
projection rather than a second source of truth.

```
BIXBY (input)        CHAT UI (create)      BOARD UI (home)
      │                    │                     │
      └────────── WebSocket to the cloud hub ─────┘
                           │
                    CLOUD (LangGraph)
                           │  dispatch / approval / control
                           ▼
                    DEVICE AGENT (harness + SK planner)
```

**Sessions are keyed by `device_id`** — one device, N UIs. UIs pick a device (`select_device`),
the choice persists in `localStorage`, and an offline device is reported rather than hidden.

---

## 3. Cloud — the goal graph

`src/goalflow_cloud/graph/nodes.py` builds one LangGraph `StateGraph`, checkpointed to SQLite
(`data/goalflow.db`) so a mid-demo restart rehydrates. The nodes:

```
interpret_goal ─► detect_constraints ─┬─► load_memory ─► present_understanding ─[interrupt]─┐
                                      │                                                     │
                                      └─► capture_gate            (a statement, not a goal)  │
                                                                                             ▼
   build_contract ─► dispatch_to_device ─► collect_plan ─► hitl_approval ─[interrupt]─► relay_decisions ─► monitor ─► finalize
```

A full run on the wire — two human gates, and the safety filter that is not one:

```mermaid
sequenceDiagram
    autonumber
    participant Bixby as Bixby (input)
    participant Chat as Chat UI (create)
    participant Board as Board UI (home)
    participant Cloud as Cloud (hub + graph)
    participant Device as Device (harness + SK)

    Device->>Cloud: hello {role:"device"} · capabilities
    Bixby->>Cloud: hello {role:"ui", surface:"input"}
    Board->>Cloud: hello {surface:"board"} · board_get
    Cloud-->>Board: board_snapshot

    Bixby->>Cloud: user_goal "plan our dinners this week…"
    Note over Cloud: interpret_goal → detect_constraints → load_memory<br/>(constraints resolved for THIS domain)
    Cloud-->>Bixby: chat_ui_open {goal_id}
    Cloud-->>Chat: understanding {objective, knew, constraints, proposed_constraints}
    Note over Chat: GATE 1 — the user confirms what it understood<br/>(a pure statement stops here: capture_gate → notice)
    Chat->>Cloud: understanding_response {confirmed, accepted_constraint_ids}
    Cloud->>Device: dispatch {objective, constraints{hard,soft}, scope, time_window}

    Note over Device: decompose → per-task plan → ground → SAFETY FILTER (code)
    Device-->>Cloud: agent_event ×N (phase · harness · thinking · tool_call · task_update)
    Cloud-->>Chat: agent_event (passthrough)
    Cloud-->>Board: board_update (folded GoalSummary)
    Device->>Cloud: plan_ready {plan, tiered proposals, safety, precheck}
    Cloud-->>Chat: present_plan
    Note over Chat: GATE 2 — approval. Nothing A2 executes before this.
    Chat->>Cloud: approval {decisions}
    Cloud-->>Bixby: chat_ui_close {goal_id}
    Cloud->>Device: approval
    Device->>Cloud: status {executed[] — including blocked_safety}

    Note over Board,Device: Later — the world moves
    Board->>Cloud: control {command:"advance_day"}  (goal-less; fans out)
    Device->>Cloud: proposal {trigger, tier, requires_approval}
    Cloud-->>Board: board_update (alert raised until answered)
```

Off the happy path: `goal_declined` (the user said no at the gate), `decline_out_of_scope`
(nothing in the product can advance it), `explain_block` (a safety refusal, explained in the
user's terms), `precheck_wait` (blocked *for now*, not forever).

Three things worth knowing:

- **The actionability gate is generic, not a domain list.** The device advertises its
  capabilities; the cloud asks the model whether the goal can plausibly be advanced *using
  those functions*. There is no hardcoded set of supported domains, and an interpreter that
  coins a new domain slug still gets the full enforced constraint set.
- **Actionable ≠ permissible.** The cloud answers *"is this in the product's world?"*; the
  device's Safety Policy Engine answers *"may it happen?"* — and produces a far better refusal.
  Running the dishwasher on Wednesday is plainly actionable; scheduled inside the away window it
  comes back blocked, *"nobody is home"* (gate 21).
- **The graph reasons in the DEVICE's day, not the machine's** (v8.1). The device runs a
  `SimulatedClock` — anchored at real today when its process starts, stepped by *Advance day* —
  and everything the user can see is dated by it: the plan's rows, the world's events, the
  board's today. The hub reads that day off frames the device already sends
  (`status.payload.sim_date`, `day_advanced.sim_date`), keeps it **per session**, and
  `start_goal` stamps it into the graph so every node calls `_today(state)` instead of
  `date.today()`. Stamped **once per run** on purpose: a goal is interpreted, grounded and
  dispatched against a single day, and re-reading the clock mid-run would let a world tick
  shift a goal's dates underneath it. Falls back to real today when no device has reported —
  which is also when nothing has been simulated, so the two agree. Gate 29.
- **The interpreter is handed a calendar, not asked to compute one** (v8.1). Given only
  *"Real today is …"* it resolved named weekdays a day early, every time (§5b). It now receives
  the next fortnight, dated and named. Gate 28 (cloud).
- **`BoardService` (`board.py`) derives board truth from frames the hub already routes.**
  Progress, next step, ETA, alerts and state are folded from device `task_update`/`status`
  frames into whole-object `GoalSummary` deltas (replace-by-id, idempotent), sequenced by
  `board_seq` with a `board_get` heal on a gap.

---

## 4. Device — the harness

`Harness/` is the generic core and holds **no product literals** — no plugin type names, no
`meal_plan`, no ingredient groups. Everything fridge-shaped lives under `Products/FamilyHub/`.
That invariant is gated (gate 3 counts the remaining product strings in the harness).

```
src/GoalFlow.Device/
  Harness/
    CapabilityManager/    [1] discovery, resolution, availability, the grounding set
    SafetyPolicyEngine/   [2] grades + declarative rules; SafetyFilter is the SK seam
    PrecheckEngine/       [3] probes + two gates — "blocked for now" ≠ "blocked forever"
    TaskManager/          [4] task DAG, lifecycle, retries, progress, IDomainObserver
    ProductApiAdapter/    [5] the seam every plugin calls instead of the world
    Approval/ Grounding/ Clock/ Trace/        supporting, not components
  Products/FamilyHub/     11 SK plugins, probes, 6 observers, config/{policy,prechecks}.json
  Agent/GoalAgent.cs      kernel host + per-goal orchestrator + both planner altitudes
```

**The planner was never extracted into its own folder.** Decompose and per-task planning live
in `GoalAgent.cs` (`DecomposeAsync`, then plan each task as it becomes ready) with the DAG in
`Harness/TaskManager/TaskDag.cs`. One planner, two altitudes; a decompose that fails to parse
falls back to a single synthesized task, which is exactly the old one-shot behaviour.

**Automation grades** replace consent tiers. `policy.json` may only make a grade *stricter* — a
loosening override fails loudly at load, so a typo cannot silently weaken the gate.

| Grade | Meaning | Example |
|---|---|---|
| A0 | executes, logged | all reads, `Reminders.Create` |
| A1 | rides the batched plan approval | `ShoppingList.Add` |
| A2 | never executes before explicit approval | `ShoppingList.PlaceOrder` |
| AX | **prohibited** — never a proposal target, blocked unconditionally, no approval path | *(no function carries it — see below)* |

**AX is a mechanism without a subject.** Nothing the Family Hub does today is prohibited: the
plugins grade A0–A2, `grades.overrides` in `policy.json` is empty, and the smart lock that was
meant to be the first AX function was never built. It is enforced twice (never offered as a
proposal target; blocked before any constraint logic) and gate 7 exercises it through a
throwaway policy that tightens `ShoppingList.PlaceOrder` to AX — so the mechanism is verified,
but there is **no AX beat to demo**.

**Safety rules are instances, not code.** The engine defines five rule *kinds* —
`blocked_terms`, `numeric_cap`, `time_window_block`, `date_window_block`, `result_screen` — and
`Products/FamilyHub/config/policy.json` holds the *instances*. Rules read `constraints.hard`
and nothing else — arithmetic that needs world state (§5, the envelope) happens once in a
policy **resolver** before the policy is armed, never inside a rule.

**An actuation has four outcomes, not three** (v8.1). `executed`, `deferred_precheck`
("not yet" — the world moved between planning and approval; the approval stands),
`blocked_safety` ("never, as asked" — the gate refused; it does not stand) and now
**`failed_actuator`**: it ran and threw. Plugins throw *deliberately* — `Deliveries.Hold`
refuses an essential delivery precisely so a refusal cannot land on the card as a completed
step — and the commonest trigger is not a plugin bug but the model naming something the
household has never had. That invoke was unguarded, so one throw left the loop **and the
handler**: later proposals skipped, nothing marked executed, and no `status` frame sent. The
goal went silent, with one stack trace in the device log.

Worse, it did not stay silent for one run. Tasks reach `Monitoring` on the **last line** of
the approval handler, so a throw stranded them in `Executing` — and completion only swept
`Monitoring`, so the goal could then never finish. Not late: never. Its card sat on the board
past its dates for the rest of the session while every other goal retired around it, which is
why the symptom looked unrelated to the crash that caused it. Completion now also sweeps
`Executing` (a goal whose last day has passed is over, however its executor ended); still
never swept are `Created`/`Ready`/`Planning`/`AwaitingApproval`, because a goal waiting on a
person is not complete and retiring it would answer for them. Gate 21 covers both halves.

**Multi-goal is real, and it was three concrete bugs.** Policy is keyed per goal with the
current goal flowed to the filter via `AsyncLocal` (a singleton `SetPolicy` once let goal B
overwrite goal A's allergens mid-plan — the worst possible failure for "code checks"); `Trace`
hands out per-goal scopes owning their own sequence; per-goal state is a
`ConcurrentDictionary` in each owner (`ArmedPolicies._policies`, `TaskManager._goals`,
`GoalAgent._pendingPatches`) — the v3 plan also called for a per-goal semaphore and it turned
out not to be needed. Monitoring, adaptation and approval run cross-goal in parallel; **device
planning is capped at one at a time**, so a queued goal shows as *Waiting* on the board instead
of stalling invisibly.

---

## 5. Constraints — the part the code checks

Household policy lives cloud-side in `data/memory/family_profile.json` as a **library of
constraint entries**, one per fact, each carrying its own provenance and lifetime. It is
resolved **per goal** and pushed down on the dispatch; the device enforces and never authors.

Seven rules, each closing off a tempting-but-wrong implementation:

| # | Rule | Why |
|---|---|---|
| R1 | Every constraint carries a **`source`**: `account`, `derived`, or `chat` | A block the user cannot trace is a block they will not trust |
| R2 | **The LLM never authors a hard constraint** — capture proposes, the user confirms | Letting the model write the policy it is checked against collapses the whole split |
| R3 | **Policy pushes down; facts are discovered up** | The account owns caps; the device owns `spent`, inventory, appliance draw. Removes the duplicated truth |
| R4 | Constraints have **scope** (household / domain / goal) and **expiry** | "$1500 travel" is per-trip; "on antibiotics, 10 days" retires itself |
| R5 | Enforcement is **household-flat** — no per-member binding | Member binding makes "who is attending" (an LLM judgement) an input to safety |
| R6 | A goal may **tighten**, never loosen or remove | Stops "actually the sodium thing is fine now" from relaxing a medical rule by phrasing |
| R7 | **The enforced set is never narrowed by relevance** | A wrong relevance pick must cost a noisy plan, never a safety miss |

**Resolution** (`memory/store.py`, deterministic code):

- **hard list kinds** — `allergens`, `dietary`, `medical`: the **union of every entry**,
  ignoring `applies_to`. Allergens ride on every goal (R7).
- **hard scalar kinds** — `budget_cap`, `quiet_hours`, `peak_hours`, `away_window`,
  `budget_envelope`: most specific `applies_to` wins (goal > domain > household); on a tie the
  **stricter** value wins where the values order at all — a lower cap is a fact about the
  numbers. Windows do not order, so on a tie the **later entry** wins: the store is
  append-only, which makes a later position literally *"said afterwards"*, and at equal
  specificity the later statement is the one a person means. It also gets the seed right for
  free, since fixtures are written first. (v8.1 — this used to keep the *incumbent* and log a
  warning, which is §5b's silent failure below. `captured_on` is not enough to order by: a
  demo states every one of these rules on the same simulated day.)
- **expired entries** drop first. Dates are **day offsets resolved against today**, so a
  seeded world never goes stale between demos.
- **soft bias** is chosen by a small structured LLM call, with `applies_to` tag-matching as
  the fallback. Soft can be wrong for free; hard cannot — which is the whole reason only soft
  goes near the model.

So a vacation goal is constrained like a vacation, which is the point of the exercise.
**Every row also carries allergens, dietary, medical, quiet hours and the envelope** — those
never vary by domain (R7), so the table lists only what *differs*:

| Domain | Hard, on top of the always-enforced set | Soft (bias) |
|---|---|---|
| `meal_plan` | — | prefers white meat, workout-friendly |
| `guest_dinner` | — | hosting style |
| `vacation_prep` | **away window** (ISO dates) | SmartThings away routine, energy saving, finish perishables |
| `birthday_party` | — | party style |
| `grocery_cost` | — | shop thrifty |
| `energy_saving` | **peak tariff window 17:00–21:00** | shift heavy runs off-peak |

**v7 emptied the household of money and quiet hours.** There is no `budget_cap`, no
`budget_envelope` and no `quiet_hours` entry any more — which retires the envelope story
along with them. That is an emptying of the STORE, not a removal of the mechanism: those
kinds are still first-class here, the device's `numeric_cap` and `time_window_block` rule
instances still enforce them, and the device gates still exercise both against synthetic
policy blocks. Nothing resolves, so nothing is dispatched, so nothing is shown. Seed an
entry and the whole chain works again unchanged.

**Display is not enforcement (v7).** An entry may carry `display_to` — the domains its
chip is worth SHOWING on. It changes nothing about resolution: the list kinds still union
with `applies_to` ignored, and `hard` is still what gets dispatched. It produces a second
block, `hard_display`, for the cards. So a home-prep goal shows no food chips while still
carrying — and still being blocked by — every allergen the household holds. **Hiding a
chip never hides a rule**, which is why they are two blocks rather than one filtered one,
and why gate 15 pairs every display assertion with the enforcement assertion beside it.

A domain with no cap of its own inherits the household default, and a slug the interpreter
coined that nobody tagged gets the full enforced set plus that default — verified by gate 15.

**The household envelope** is what makes goals share a wallet. The cap is policy; the spend is
world state, so `budget.json` keeps `spent` and no longer restates the cap (R3):

```
effective cap = min(domain cap, monthly envelope − spent)
```

Resolved at arm time and **re-resolved on approval and on each day tick**. Approving the party
order shrinks the grocery goal's headroom and drives that goal through its existing adapt path
— one wallet, visible across goals. A resolver that throws arms the *dispatched* policy: a bad
world read loses the tightening, never the gate.

**Capture from chat.** *"We've gone vegan"* is a statement, not a goal. It routes to
`capture_gate`, rides the existing understanding card with `capture_only: true` (per-rule ticks,
the user's words quoted back, an ENFORCED badge, no board card), and only what was ticked is
written — with `source: "chat"`, append-only, tighten-only. A diet's *name* is expanded into
what it forbids, because the device's vocabulary matches things, not labels: "captured but
unenforceable" is the one outcome capture must never have, and from the UI it looks identical
to success.

### 5b. One goal changing another (v7)

The household envelope was the first cross-goal channel and it moved a *number*. The
second moves a *plan*.

Approving a home-away goal writes its window to the store as a **household-scoped,
chat-sourced, self-expiring** entry — until approval it is a proposal binding only itself;
approval makes it a fact about the household. **Only if that goal AUTHORED it** (v8.1):
`contract.constraints.hard` is the *resolved* set, so it carries a live household window the
goal merely inherited, and promoting that meant every goal re-promoted what it had just read
— a *Weekly Meal Plan* wrote two household away windows this way, one of them seven days
long. Authorship is decided by asking what the household already holds for *everyone*
(resolving against the empty domain matches `applies_to: ["*"]` and skips domain-scoped
entries): if this goal's window is already in that set, the goal is a reader. The cloud then
re-resolves every other
active goal and, where the enforced set actually moved, sends
`control: constraints_changed` carrying the account's new `constraints.hard`, a steer, and
one sentence for the board. The device re-arms from what it was sent (`ReDispatchAsync` —
distinct from `ReResolveAsync`, which recomputes what is *enforced* from an unchanged
dispatched block; re-resolving from a replaced block would let the device's own narrowing
compound, and replacing on a re-resolve would let the device author policy) and applies the
patch **immediately**.

**This is the only adaptation path that does not ask, and the reason is not convenience.**
Every other change in the system is something the *world* did, so a person decides what to
do about it. This is something the person already decided, arriving at a goal that had not
heard yet. *"You said you're away Thursday — shall I stop planning dinners for Thursday?"*
is a question whose honest handling is not to ask it. So the plan changes and the board
**says so**: one informational line on the card, a dismissible notice on the detail page,
and never an alert — an alert means "you still have to decide".

The days themselves are **kept, not deleted**. `PlanItem.status: "skipped"` renders them
greyed with their reason; a plan that merely got shorter says nothing about why, and reads
as data loss rather than as a decision. Gate 17 pins the blast radius, the idempotence and
the self-retirement; gate 25 pins that the account still owns the policy.

**And they stay empty.** A skipped day is not a hole for the next world event to fall into.
The first version of this shipped without that rule and the demo undid its own headline one
interaction later: the family approved the trip, both days went to "Away — no meal planned",
and the next press of *Advance day* fired "the paneer spoiled" — whose steer says *change
tonight's dinner* — against a day nobody is home. Two layers close it, because one is a
judgement and the other is a guarantee: the observer stops raising such a change as
material (so no re-plan is even attempted, and no approval is opened), and
`DropSkippedRows` refuses any patch row whose incumbent is skipped, whatever produced it.
The single exception is `constraints.changed` itself — the path that writes skipped rows is
the only one that may clear them, or a cancelled trip could never give the family their week
back. The change is still **told**: it stays in "what happened today" with the reason
appended, because a family that is away still wants to know their fridge lost something.
Gate 26 pins all three.

**The webview outlasts the save.** `chat_ui_close` used to follow the approval within a
round-trip, so the "Saving…" screen existed in the code and never on screen. The dwell
cannot live in the chat UI — Bixby unmounts the webview the moment the close arrives, so a
hold inside the iframe is a hold nobody sees. The cloud owns the bracket and therefore the
dwell: a floor for the ordinary hand-off, and for a household change, a bounded wait until
the re-planned goal actually reports back, so the user reaches a board that already has the
change. Gate 18 pins the floor, the wait and the bound.

**It failed silently three times, and each cause was invisible because every individual step
was right** (v8.1). Worth recording, because this path has no error state — it either changes
another plan or it does not, and "did not" looks exactly like "nothing needed to move".

1. **The window itself was a day early.** `_align_away_window` takes `intent.time_window`
   VERBATIM, and the interpreter, handed only *"Real today is 2026-08-02 (Sunday)"*, resolved
   **every** named weekday one day early — *Tuesday and Wednesday* → Mon–Tue, four for four at
   temperature 0. It was not misreading a calendar; it was not consulting one. It is now given
   the next fortnight, dated and named, so a weekday is a lookup: 20/20 across five anchors.
2. **The cloud was on the wrong day.** The device runs a `SimulatedClock` stepped by
   *Advance day*; the cloud called `date.today()`. The two agree until the second minute of a
   demo. The hub now learns the device's day from frames it already sends
   (`status.sim_date`, `day_advanced.sim_date`), stamps it into the graph **once per run**, and
   every node reads it (§3). Per home — two devices can sit on different simulated days.
3. **The new window was written, logged, and invisible.** Two household windows at equal
   specificity, and resolution kept whichever came first (§5). So every other goal went on
   resolving the *old* dates, the fan-out compared each goal's enforced set before and after,
   found them identical, and correctly concluded nothing had moved. Nothing had.

Gate 17 gained the authorship and newest-wins cases it lacked through two rounds of this;
gates 28 and 29 (cloud) pin the calendar and the clock.

**`GOALFLOW_PROFILE_PATH`** points the store at a scratch copy — the cloud's equivalent of the
device's `--data`. A path that does not exist yet is seeded from the committed profile on first
use, so a demo run never dirties the seed.

---

## 6. The wire

**`goal-flow-cloud-agent/CONTRACT.md` is canonical.** Everything else mirrors it, and a frame
change touches every mirror in one pass:

`CONTRACT.md` · `models/contract.py` · **three** UIs' `src/types/contract.ts` (chat, board,
bixby) · `Contracts/*.cs` ·
and **`ws.ts INBOUND_TYPES`**, a client allowlist that *silently drops* unlisted frames. Gated
by `scripts/verify_mirrors.py`.

Shape, at a glance: `hello`/`hello_ack` · `devices`/`select_device` · `capabilities` ·
`user_goal` · `understanding`/`understanding_response` · `notice` · `chat_ui_open`/`chat_ui_close`
· `dispatch` · `agent_event` (the live stream: `phase`, `thinking`, `tool_call`, `tool_result`,
`task_update`, `harness`, `plan_progress`) · `plan_ready` · `present_plan` · `approval` ·
`proposal` · `status` · `control` · `day_advanced` · `board_snapshot`/`board_update`/`board_get` ·
`goal_state_get` · `goal_accepted`.

**Surface-aware delivery.** A `hello.surface` of `"input"` receives only `hello_ack`,
`goal_accepted`, `chat_ui_open`, `chat_ui_close` and `notice` — Bixby is a native app that would
parse and drop everything else. `"chat"` and `"board"` stay on the full session broadcast (their
split is *temporal, not type-based*) and their client allowlists filter. An absent surface means
everything, so older clients are unaffected.

**The create-phase bracket.** `chat_ui_open { goal_id }` is emitted before `understanding` and
opens (or retargets) the webview; the chat UI treats it as a hard reset keyed to that
`goal_id`. `chat_ui_close` fires on the **initial approval** — the user's final tap — and also on
a declined gate, a completed capture (there is no plan coming), and any terminal error after the
open, so the webview can never dangle. Every close is guarded on "still the session's
create-phase goal", which is what stops a board adaptation approval from retriggering one. A per-session replay cache (`understanding`,
`present_plan`) is replayed to a freshly-bound `"chat"` socket, which is what fixes the race
between the webview connecting and the understanding being computed.

---

## 7. The surfaces

**Bixby (input)** — where the user types. The chat UI has had no composer since v4.1.

**Chat UI (create phase)** — the theater. One **working column** for the passage of work:
receipts above (each engine's verdict and its measured wall-clock), exactly **one focus card**
holding the live transcript and tool-call chips, ghosts below for what hasn't run. The goal
itself is the page title, with the run clock opposite it. Then the plan lands row by row into
reserved slots, with tiered approvals under it.

Three rules keep that honest, and each of them was learned the hard way:

- **Cards size to their content; the column scrolls.** This took three tries. v5.1 conserved
  total height by letting the focus card absorb every spare pixel — mathematically neat, and it
  put a one-line note in a box half the screen tall. Fitting the content fixed that but kept the
  never-scroll promise, which the plan card cannot make: seven steps plus approvals exceed any
  viewport, and a clipped "Approve" is far worse than a scrollbar. So v5.2 lets the **content**
  scroll while the goal bar stays put — and pins `.column__main > * { flex: 0 0 auto; }`, because
  flex items shrink by default and a squeezed box whose content kept painting drew the cleared
  pipeline straight through the plan card. The transcript has its own `max-height: 220px`.
- **The record outlives the wait for it (v9).** When the plan arrived the focus card
  unmounted and took the model's prose with it — the one artefact showing the goal was
  *reasoned* about rather than looked up existed only while you were waiting, and was
  deleted at the moment you had time to read it. The compact strip now carries a second
  collapsed bar under the pipeline, *"How it thought · N tool calls"*, holding the same
  transcript (one definition, rendered in two places) at `max-height: 340px` — settled, it
  is a document rather than a tail being watched. Closed and second, because the plan is
  the hero once the run is over, and rendered only when the run left words behind.
- **The planner stopped being silent (v7).** `ComposeModelPlanAsync` is not streamed and
  keeps its plan JSON off the thinking channel deliberately, so through v6 that engine
  emitted *nothing* on a healthy run — the drawer was blank for the longest stretch of it,
  and a silent engine is indistinguishable from a broken one. It cannot narrate what it is
  thinking, but it can say what it is thinking AGAINST: `thinking` gained optional
  `kind`/`step`/`detail`, and a **step is whole on arrival**, never a fragment, so a client
  renders it rather than accumulating chunks and guessing where a thought ends. `text`
  stays the only required field, so a pre-v7 surface renders exactly what it did before.
- **The transcript belongs to one engine** — attributed to the engine live *on the wire*, never
  the painted one, which lags behind by the render floor. Without this, Planner and Safety
  repeated grounding's narration as if they had said it. Which matters more than it sounds: over
  a full ~3-minute run the device streams about **578 bytes** of prose, nearly all of it in one
  burst during grounding. The "it's working" signal through the quiet stretch is the tool-call
  chips and the accumulating receipts, not text.
- **Durations tell the truth.** Stamped on *arrival* off the wire, not at paint, so our own
  pacing never plays back as the device's work — and under 100 ms nothing is printed at all,
  because "0.0s" next to an engine that did real work is a worse lie than silence. The render
  floor is a paint-timing knob only; order, verdicts and reported latency are exactly what the
  device sent.

**Board UI (home)** — one card per goal, leading with the outcome plus ✓ done / ⏳ waiting /
➡ next. **v7 took the tool calls out of it** — the capability chips, the
`{module}.{function}` beside each action, and the raw `Plan.ApplyPatch` in the history,
which was the string every adaptation logs, so the one line telling a person their week
changed said it in the language of a method call. This is the board: where someone looks
to find out what is happening to their week, not to watch an agent work. The chat keeps
its chips, because watching it work is what that surface is *for*. The evidence moved
rather than vanishing — the why on every plan row, and the considered/rejected line under
the plan, say the same thing in the reader's language. **It is a first-class surface, not read-mostly** — v3 designed it as a projection that
never wrote, and v3.1 reversed that: the goal's whole life after creation happens here.

It sends `hello`, `select_device`, `board_get`, `goal_state_get`, `user_goal`,
**`approval`** (adaptations, on the goal-detail page) and **`control`**
(**Advance day** — one global world tick, a goal-less frame that fans out over every active
goal, landing on the day it advances to with real dates like "Tue, Jul 22"). It never sends
`dispatch`: the hub-only invariant holds.

The split with the chat UI is **temporal, not by capability** — chat owns *creating* a goal
(understanding gate, first plan, first approval), the board owns everything after. A card
drills into the chat app with `?goal=<id>` for the detail view.

---

## 8. The demo world

Mocked, offset-relative, and deliberately small. Six domains have observers, so six kinds of
goal can adapt: `meal_plan`, `guest_dinner`, `vacation_prep`, `birthday_party`, `grocery_cost`,
`energy_saving`. Eleven SK plugins stand in for the product APIs (Inventory, Recipe, Calendar,
ShoppingList, Budget, Appliance, Security, Notify, Reminder, Guests, FamilyProfiles).

**No absolute dates anywhere** — the world is day offsets against a mock clock, so the demo
works on any day without editing fixtures.

The negative paths prove the harness better than the happy ones. Three are real:

- a **precheck failure** — flip `device_online:<appliance>` to false in `device_state.json`
  (dishwasher, oven or fridge — **there is no thermostat in this world**, despite the example in
  the engine's own comments) and that subtask parks At Risk while the others proceed, resuming
  when the probe clears;
- a **window block** — an appliance run scheduled inside the away window, or a heavy one inside
  the peak-tariff window on an energy goal, comes back blocked with the reason. These are the
  most reliable to show because they bite at **approval** time and need no cooperation from the
  planner;
- the **envelope squeeze** — another goal's spending moves this goal's ceiling and it re-plans.

A **safety block with recovery** (a too-expensive cart blocked, the model visibly re-planning a
cheaper one) is real but depends on the planner proposing the expensive cart in the first place,
so it is not something to promise from a stage. The **AX refusal** the v3 plan wanted is not
demoable at all — see §4.

**Proactive suggestions were removed in v7.1.** The device scanned its own inventory and
offered goals nobody asked for — expiring food, low stock — as an "Upcoming & Suggested" strip
above the goals. The mechanism worked and the strip was noise: it appeared unbidden next to
work the user had actually commissioned, and on a board whose whole claim is "these are the
goals you gave me", a card the user never asked for is the one thing that has to earn its
place. It didn't. The device scan, the `suggestions`/`suggestion_action` frames and the
board's section are all gone.

---

## 9. Verification

Gates, not tests, and the rule is that **a gate you have not broken is a gate you do not
trust** — every one of these was falsified before it was believed.

**Device** — `verify/*/check.sh`, each chaining the previous. `./verify/v9/check.sh` runs the
whole chain, no API key needed. Highlights: gate 3 (harness product-string debt), gate 5
(per-goal policy isolation), gate 6 (28 safety-rule cases), gate 7 (grade ratchet + AX), gate 8
(task lifecycle + DAG), gate 9 (prechecks), gate 11 (trace isolation), gate 19 (one cap, from
the account), gate 20 (two goals, one wallet), gate 21 (a refusal is reported as a refusal),
gates 22–26 (the v7 chain, ending with an away day staying away), gate 28 (no grounding read is
asked twice, and a tool that cannot satisfy a query says so), gate 29 (the request shape:
`provider` and `reasoning_effort` on the wire, and invisible until asked for), **gate 30 (a
429 waits seconds, everything else still waits 400ms, and the cool-off is a floor)**. Gate 18
is RETIRED — it
gated the proactive-suggestion scan, which v7.1 removed; `verify/m8/check.sh` survives as an
empty link because v6-m2 chains it.

**Cloud** — `python scripts/verify_*.py`: gate 10 generic actionability, 12 persistence across
restart, 13 board fold (incl. v7.1's retire-on-advance-day), 14 contract mirrors, 15 constraint
resolution, 16 chat capture, 17 cross-goal blast radius — plus, since v8.1, *authorship* (a goal
carrying an inherited window must not re-promote it) and *newest-wins* (a second window at equal
specificity must actually reach the other goals) — 18 the webview outlasting its save,
27 a refusal reaching its webview, **28 a named weekday means that weekday**, **29 the cloud
reasons in the device's day**. Everything but 10 and 12 needs no API key; gate 28's interpreter
half needs one and SKIPS without it rather than passing, because a gate that cannot run must not
be able to pass either.

*The two numbering spaces are independent and they collide* — device gates 15/16 are the
provider deadline; cloud gates 15/16 are constraints and capture. Say which side you mean.

**Tizen is the trap.** A clean `dotnet build` does not prove the port works: DI resolves at
runtime, so a copied core can compile perfectly against a host that cannot construct its
plugins. Twice now, host wiring has hidden behind a green build. A re-sync is: wholesale core
copy → host wiring in `DeviceHost.cs` → data → check the safety config is packaged. Tizen also
has no console (use dlog), no env vars (use `goalflow.conf`), and a read-only resource dir
(seed writable data on first run).

---

## 10. What changed, by version

Brief by design. The detail is in the code, the gates, and `git log`; the pre-merge tags
(`pre-v5`, `pre-v5.1`, `pre-v6`) are the revert points.

| Version | What changed |
|---|---|
| **v1** | The original meal-plan demo: one goal, one shot, cloud + device + a chat UI. Proved the two-tier pattern. |
| **v2** | Reframed from meal planning to a *general* goal agent. Named 11 harness modules; capability vs steering modules; the use-case catalog. |
| **v3** | The harness becomes **five first-class components**; device-side two-altitude planning; **multi-goal** (which meant fixing a real cross-goal safety-gate clobber); persistence; the **Agent Board** as a new repo. M0–M9. |
| **v3.1–v3.6** | Board-centric flow (chat creates, board runs); one **global Advance day** replacing per-goal event strips; the **five locked demo use cases** across six domains; the planner made generic per domain instead of meal-shaped; goals-first board cards. |
| **v4.1** | **Bixby becomes the entry point** (new dev surrogate repo; the chat UI loses its composer): surface-aware delivery, the `chat_ui_open`/`chat_ui_close` create-phase bracket, and a replay cache. |
| **v4.2** | Advance-day edits the day you land on, with real dates; quieter device/cloud logs; thinking becomes a live "watch it think" transcript. |
| **v5** | Made the harness **visible** — a `harness` agent_event kind and a live pipeline panel — plus a unified light-grey theme and presenter dwell. Then fixed the tail engines flashing past, since their real work precedes their beats. |
| **v5.1** | The chat surface becomes **one working column**: receipts, a single focus card holding the transcript, ghosts. Durations stamped on arrival, paced plan reveal, `plan_progress.total`. |
| **v5.2** | The panel redesign (confirm / run / plan, from `goal-flow2.pen`): the constraint chip grid, a motion vocabulary in `panel.css`, and the column learns to **scroll** — v5.1's never-scroll guarantee could not survive a full plan plus its approvals. |
| **v6** | **Constraints with provenance** (§5): sourced, scoped, expiring, resolved per goal; cloud/device de-duplication; the household envelope across goals; capture-from-chat behind a confirmation gate. M1–M4. |
| **v7** | The demo cut to **two goals and a refusal**, and the mechanisms that story needed. The household lost money and quiet hours entirely (§5). Display split from enforcement, so a goal can show no chips while still being blocked by every rule it carries. Preferences and provenance reached the screen for the first time. The planner stopped being silent (§7). **One goal now changes another** without asking (§5b) — the demo's headline. Activity data, deliveries and a robot vacuum joined the world; the board stopped speaking in function names; a refusal got a surface. M0–M7. |
| **v7.1** | Five things the demo asked for after a live run. Proactive suggestions deleted outright — device scan, frames and board section (§8). A finished goal now leaves the board on the next Advance day. The refusal's webview was opening EMPTY: the `notice` was broadcast while Bixby was still mounting the iframe, so terminal notices joined the create-phase replay cache (gate 27). The device's decompose pass learned the domain — only compose knew it, so a home-away goal was being broken into meal steps by a model reading the household's food rules. And in *Show details*, an engine's prose now precedes the steps it announces. |
| **v7.2** | Grounding stopped asking the same question over and over. A meal plan was spending ~4.5 minutes on ten-plus `Recipes.FindRecipes` calls that differed only in the ORDER of the tag list: the household prefers white meat, the recipe box is entirely vegetarian, and the tool answered a query it could not satisfy by returning everything in an unchanged order — indistinguishable, to a model, from "these are your best matches". Now the tool names the tags it could not match and says not to search again; a `RepeatReadFilter` makes any identical read (permuted list arguments included) cost one round-trip; and `AllowParallelCalls` is finally true, so independent reads batch into one turn instead of one round-trip each. The seed gained five recipes — three white meat, two red — because a preference with nothing to turn down is invisible: the plan now leads with chicken/turkey/fish and rejects beef and lamb *on the preference* while pork is rejected *by the hard rule*, two different kinds of no in one list. Measured on the same prompt: **336s+ and still looping → 148s to a finished plan**, 10+ recipe calls → 1. Gate 28. |
| **v7.3** | The planner's own error — *"Planner did not return any content for the JSON plan"* — traced to two things and one wrong assumption. (1) `response_format: json_object` returns empty content on the COMPOSE call, though the same model honours it fine on a short prompt and on decompose; the verdict is now learned per call-site from the real call and the wasted round-trip is paid once per process, not per plan. (2) Compose's 6000-token ceiling covers reasoning AND output, and the reasoning alone was consuming all of it — `Completion tokens: 6000` exactly, twice, empty. Raised to 16000; a starved budget was wearing the mask of a modelling failure. (3) `GetRecipe` was being called once per recipe after `FindRecipes` had already returned them in full — seven redundant round-trips, now closed by saying so in the descriptions. The wrong assumption: raising GROUNDING's cap the same way took that phase from 77s to 253s and hit the new cap too, so it is reverted and the negative result is recorded in the constant. Measured: **117.9s** to a plan, zero planner notices. |
| **v7.4** | The create bracket opens on ARRIVAL, not after interpretation. `start_goal` is a 10-60s LLM round-trip and `chat_ui_open` was emitted after it, so the slowest wait in the product happened with no webview on screen at all — the user spoke to the fridge, the fridge showed nothing, and the understanding card then appeared as if the work had been instant. Measured at **43.6s** of blank screen. The open now fires at 0.0s carrying `goal_text`, so the panel shows the user's own words under a *"Reading your goal…"* state with a rotating live line, a running clock and the seven engines listed as *ready* rather than *0 of 7 cleared*. The error path closes the bracket it now inherits; the refusal path no longer re-opens it (a second open would wipe the panel the user has been watching). |
| **v7.5** | Three from a run-through. The **interpretation screen drops the pipeline** — seven grey rows all saying *queued* under a heading that counted nothing, inviting the reading that seven things were stuck when none had been asked to start. The **saving screen gains an indeterminate progress bar**: the cloud holds it until another goal has actually re-planned, so there is no percentage to be honest about, but 20-30s is more than a lone spinner carries. And the **card's date now moves with the world clock** — `subtitle` was written once at dispatch and never again, so every Advance day left it saying exactly what it said before. Loudest once the date had passed, which is where it was reported: a meal week stuck on *Sun, Aug 2* while the world was on Aug 5, indistinguishable from a card that had stopped updating. The home-away card looked fine beside it only because its deadline was still ahead. Now *Fri, Aug 7 · 4 days left* → *last day* → *Ended Fri, Aug 7*, rebuilt from the same window and sim_date that already move the progress bar, so the two cannot disagree. |
| **v7.6** | Two found on the **Tizen Hub**, both of which the dev box could not have shown. (1) A confirmed understanding stayed in the create-phase replay cache until a plan replaced it, so any chat socket reconnecting during planning was handed back the gate it had already answered — the surface jumping backwards mid-run. The trigger is a mid-plan reconnect, not the platform: a dev box holds its socket for the whole run, a Hub webview does not. Latent since v4.1; gate 27 now covers it. (2) `.app { height: 100dvh }` — `dvh` is Chrome 108, newer than the Hub's webview, which drops the declaration entirely. Measured: the shell collapses 1920px → **160px**, taking the absolutely-positioned saving overlay with it and leaving the body's near-white gradient — the "blank white saving screen", and the reason the layout never filled the panel. A `vh` fallback ahead of `dvh` fixes both; the on-device confirmation is still owed. |
| **v7.7** | Two subtractions. **Theater and Flow are removed** from the chat surface — stage machinery for a demo that no longer needs it, and on a Hub two controls a family could tap into a state with no way out. Taken out whole (HarnessTheater, PresenterFeed, the raw-frame buffer they fed, and the `FlowFrame` type), not just hidden. And the **device name appears only when there is more than one device** — on both surfaces it was a dev machine's hostname on the family's screen, wired to a picker with a single entry. The chip still returns for a real choice, and whenever the connection is not open; the board's offline notice still names the hub that went away, because there WHICH hub is the point. |
| **v7.8** | *Show details* stopped flickering, and the board lost its Harness Activity card. The flicker was the tail-follow racing itself: `scrollTo({behavior:"smooth"})` on every streamed token chunk, dozens a second, each smooth scroll interrupted and restarted before it arrived — a live log tail should stay pinned, not animate, so it is now instant, coalesced to one rAF, and only follows when the reader is already at the bottom. Two multipliers went with it: the run clock re-rendered the card 10×/s for a display that changes 1×/s, and `buildTranscript` ran on every one of those renders while its memoized sibling did not. The **Harness Activity** ribbon is removed — harness internals on the screen a family uses to see their goals; the reducer's fold stays, because gate 14 requires every `agent_event`-handling surface to handle all seven kinds. |
| **v8** | **The demo was slow because nobody had chosen an inference provider.** Four identical standalone runs on one afternoon took **59s, 175s, 145s and 189s** — same command, same input, same model. The variable was the endpoint: with no `provider` field OpenRouter load-balances `gpt-oss-120b` across nineteen providers whose throughput spans **39x**, and it kept picking the slow tier (CoreWeave 52 tok/s, Novita 76, against Cerebras 1523). Benchmarked alone, the same compose-shaped task ran in **50.1s unpinned and 1.5s pinned**. Pinning Cerebras: those four runs become **8.4 / 8.4 / 8.7 / 10.1s**, grounding 37.9-95.0s → 4.6-5.7s, compose 7.3-120.3s → 1.9-2.7s, cloud interpretation 19.7s → 2.3s, and the run-to-run spread 3.2x → 1.2x. Per goal, spoken to plan: **~225s → ~11s**. Not one prompt changed. Two negative results are recorded so they are not retried: `reasoning_effort: low` collapses reasoning from ~1400 tokens to 26-89 and made **every** benchmarked run return an invalid plan, while `medium` and the provider default are within 0.2s of each other once the provider is fast — so the knob is built, documented and shipped OFF. And an early version of the cloud measurement used a two-module capability digest and showed **no difference at all**, because a small prompt is fast on a slow provider too; it took the real 20-module digest to show the 8.5x. Also fixed, as defects rather than latency: compose's retry budget was per-attempt so three ceilings plus backoff could spend ~9 minutes on one goal (now one clock for the whole loop); the grounding tool loop had no bound at all, falling back to SK's 128 (now capped at 24, and the **round count is logged** — it was the unmeasured thing that varied 80s-240s); decompose was asking for compose's 16000 tokens to return eight task titles; and `relay_agent_event` was writing **1.19 GB of synchronous SQLite per goal** on the event loop, ahead of the UI relay, into an `event_log` written in five places and read in none. Streaming compose was designed and **rejected**: ~85% of what it emits is reasoning tokens SK cannot surface, and it would have destroyed the outcome column's exact slot reservation to light up the last fifth of a wait that is now two seconds long. **Cost was measured too, and the cheap options all lose**: Cerebras is the DEAREST endpoint for this model ($0.35/M in against CoreWeave's $0.03) but every alternative run through the real pipeline costs 20-60x the wall-clock to save about a cent — groq 234s, nebius 203s, deepinfra 551s, against 8-10s — and `gpt-oss-20b` is not cheap at all, it returns an EMPTY grounding summary the pipeline then plans around. A goal costs ~1.5 cents; the genuinely free path is the offline gates. That measurement is also why **`allow_fallbacks` is FALSE**: the next-best provider is slower than no pinning at all, so a fallback is a silent four-minute stall rather than a degrade, and failing visibly is the better demo. **Both device repos are now pinned to SK 1.43.0 exactly** — Tizen cannot move (Tizen 12 ships its own System.Text.Json 8.x as a platform assembly and SK ≥1.61 wants 10.x), so Ubuntu matches it rather than the reverse; it had been floating on `1.*` and had drifted 1.33→1.78 unnoticed, which only started to matter when v8 became the first code to need a post-1.43 API. `provider` therefore travels on the HttpClient (`OpenRouterBodyHandler`) rather than through SK, which works on any SK version and keeps the two device cores byte-identical. |
| **v8.1** | **The cross-goal moment failed silently three times, and each cause was invisible because every individual step was right.** The interpreter resolved named weekdays a day early — *Tuesday and Wednesday* → Mon–Tue, four for four at temperature 0 — because it was told the date and left to do the arithmetic; it now gets a dated fortnight and scores 20/20 across five anchors. The cloud was reasoning on `date.today()` while the world ran on the device's `SimulatedClock`, which diverge the second anyone presses *Advance day*; the hub now learns the device's day off frames it already sends and stamps it into the graph once per run. And a newly promoted household window was written, logged and **invisible** — two entries at equal specificity, and resolution kept whichever came first — so every other goal went on resolving the old dates, the fan-out found each enforced set unchanged, and correctly concluded nothing had moved. Nothing had. The store is append-only, so a later position is *"said afterwards"*: at equal specificity the later entry now wins. A fourth cause kept it coming back — the fan-out promoted whatever `away_window` sat in the approved goal's *resolved* constraints, with no check that the goal introduced it, so every goal re-promoted what it had just read and a *Weekly Meal Plan* wrote two household away windows, one seven days long. Once a stale window covers the week the idempotence guard makes the real approval write nothing, and the demo stops working with no error anywhere. **On the device, an actuator that threw took the goal down with it** — plugins throw deliberately, the invoke was unguarded, and one throw skipped every later proposal and sent no `status` at all. It then outlived itself: tasks reach `Monitoring` on the handler's last line, so they stranded in `Executing`, and completion swept only `Monitoring` — the goal could *never* finish, and its card sat on the board past its dates for the rest of the session. Fourth outcome `failed_actuator`; completion sweeps `Executing`. **Four UI fixes** rounded it out: the plan now waits for the harness to finish speaking (v8's latency had them arriving together, two things claiming to be the front of the run); the blank page after *Approve & Save* was two bugs wearing one face — the saving screen hung off *unanimous* approval when firm proposals are opt-in, and was positioned against a shell that drops to `height:auto` below 720px, centring itself a screen and a half above the reader; a redaction marker stopped printing an internal object's field names mid-paragraph; and the board's detail page stopped saying the same thing twice, while *"Got it"* finally cleared the line it acknowledged. Gates 28 and 29 are new (cloud); 17 and 21 gained the cases they had been missing through two rounds each. |
| **v9** | **A UI audit, and the record of the run made to survive it.** Contrast first: `--ink-faint` was **2.74:1** on white while carrying every eyebrow, count, caption and note in the panel — a fail at AA and AA-large, on a door read from 1-2 m — so it becomes an alias of `--ink-quiet` (4.51:1) and all ~48 call sites are fixed at once; `--stroke-strong` arrives for control boundaries, because `--stroke` is 1.23:1 and the Decline button drawn with it read as *disabled*. 26 distinct font sizes (0.75/0.76/0.78, 0.92/0.95 — pairs nobody can tell apart but must still choose between) become **seven fluid steps**. Emoji and bare text glyphs become an inline `Icon` set, so a family mark can take its family's colour and a chevron can *turn* rather than being swapped for `⌃` (U+2303, the Mac control key). **A constraint and a preference stop looking like the same object** — the one thing the confirm gate exists to teach — a tinted box with a disc and a lock against a bare row in a dense list, and the constraint grid drops to one column because an odd count rendered as a half-width orphan. **One live region, not five**: spinner, progress bar, elapsed counter, goal-bar clock and engines-cleared hairline all described a single fact, and the run has no honest percent or ETA, so only the spinner survives and the duration lands once, settled, beside the plan it produced. The refusal gets a **Close now** button and a countdown that is real (`closes_in_s` off the wire, linear, absent when the cloud scheduled no close). Then, from a live run: the goal bar and the heading were printing the same sentence twice, because the understanding frame overwrote what the user said with the cloud's restatement of it. Finally, two subtractions and an addition. **Provenance captions are gone** — every constraint said *"Account · always enforced"* and every preference *"Account · relevance"*: a caption identical on every row is furniture, and *relevance* is the internal name of our own selection pass. The data stays on the wire; it was the display that was noise. **The transcript now outlives the run** (§7). And on the device, **a 429 is not a dropped socket**: every retry site waited 400ms x attempt, so three grounding attempts against a quota window measured in seconds were spent inside ~1.2s and produced three raw-exception notices instead of a plan. Rate limits back off in seconds (2s, 4s… capped, jittered), `Retry-After` wins over the guess, everything else keeps its 400ms, and one process-wide cool-off — a floor, never a rollback — means a throttled run slows down once rather than at grounding *and* compose. Gate 30. |

---

## 11. Harness provenance — 13 specified, 5 built

The harness came from two Samsung-side input documents. They are no longer in this repo (the
mocks survive as `harness/agent-board.jpeg` and `harness/agentic-arch-execution-fw.png`), and
this section exists because **a component that was deliberately not built leaves no trace in
the code** — so this is the one fact grep cannot answer.

The TDS specified **13 components** and a folder per component. Five were made first-class,
because those five are the ones that carry a real invariant. The other eight were folded into
existing seams rather than given empty folders:

| Specified | Where it went |
|---|---|
| Goal Planner | `Agent/GoalAgent.cs` — both altitudes; never got its own folder |
| Capability Manager | **built** — `Harness/CapabilityManager/` |
| Capability Registry | folded into Capability Manager (discovery is its other half) |
| Context Manager | `Harness/Grounding/` |
| Memory Manager | cloud-side — the constraint store (§5) |
| Safety Policy Engine | **built** — `Harness/SafetyPolicyEngine/` |
| Permission Manager | `Harness/Approval/` + automation grades. Identity/roles were dropped with R5 |
| Pre-check Engine | **built** — `Harness/PrecheckEngine/` |
| Workflow Orchestrator | folded into Task Manager — the DAG *is* the orchestration |
| Task Manager | **built** — `Harness/TaskManager/` |
| Event Manager | `Harness/Clock/` + `Harness/Trace/` + `IDomainObserver` |
| Product API Adapter | **built** — `Harness/ProductApiAdapter/` |
| Telemetry & Logging | `Harness/Trace/` + structured logging on both tiers |

Two of the input documents' claims were **not** followed, deliberately: the infographic said
the cloud creates the execution plan (its own component list puts Goal Planner on the device,
and §1 above is why the device wins), and the suggested project structure would have produced
thirteen folders, several of them empty. Resisting that was an explicit v3 risk item.

---

## 12. Conventions

- **Confirm before phase jumps.** Every phase leaves durable artifacts behind.
- **Branching:** `master` is trunk. An integration branch per version (`v6`), milestone
  branches off it merged `--no-ff`. Push only integration branches and `master`. Before
  merging `vN` → `master`, tag the pre-merge master `pre-vN`.
- **Each repo has an `AGENTS.md`** — read it first in a coding session. It is the entry point;
  this document is the map.
