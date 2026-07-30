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
  **stricter** value wins, and two windows keep the incumbent and log, because windows do not
  order meaningfully.
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
| `meal_plan` | grocery cap **$120** | dislikes, weekday-vegetarian, prefer vegetables |
| `guest_dinner` | grocery cap (quiet hours bite here — the dishwasher) | hosting style, guest diets |
| `vacation_prep` | **travel cap $1500** · **away window** (ISO dates) | hold deliveries, eco while away, use up perishables |
| `birthday_party` | **party cap $200** | hosting style, kid-friendly |
| `grocery_cost` | grocery cap | substitutions, bulk staples |
| `energy_saving` | **peak tariff window 17:00–21:00** | eco programs, off-peak shifting |

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
`goal_state_get` · `goal_accepted` · `suggestions`/`suggestion_action`.

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
➡ next. **It is a first-class surface, not read-mostly** — v3 designed it as a projection that
never wrote, and v3.1 reversed that: the goal's whole life after creation happens here.

It sends `hello`, `select_device`, `board_get`, `goal_state_get`, `user_goal`,
`suggestion_action`, **`approval`** (adaptations, on the goal-detail page) and **`control`**
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

**Proactive suggestions** come from deterministic device reads (inventory low, expiring soon)
sent as `suggestions` and folded into cards by rule — no unprompted LLM calls. Tapping **+**
synthesizes a `user_goal` through the normal pipeline, understanding gate and all.

---

## 9. Verification

Gates, not tests, and the rule is that **a gate you have not broken is a gate you do not
trust** — every one of these was falsified before it was believed.

**Device** — `verify/*/check.sh`, each chaining the previous. `./verify/v6-m3/check.sh` runs the
whole chain, gates 1–21, no API key needed. Highlights: gate 3 (harness product-string debt),
gate 5 (per-goal policy isolation), gate 6 (28 safety-rule cases), gate 7 (grade ratchet + AX),
gate 8 (task lifecycle + DAG), gate 9 (prechecks), gate 11 (trace isolation), gate 19 (one cap,
from the account), gate 20 (two goals, one wallet), gate 21 (a refusal is reported as a refusal).

**Cloud** — `python scripts/verify_*.py`: gate 10 generic actionability, 12 persistence across
restart, 13 board fold, 14 contract mirrors, 15 constraint resolution, 16 chat capture. Gates
15 and 16 need no API key, because the capture write path has no LLM in it.

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
