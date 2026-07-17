# GoalFlow v3 — Design Proposal (harness + Agent Board)

v2 proved the orchestration pattern: a cloud agent interprets a fuzzy goal, a device agent plans it with
Semantic Kernel against a mocked fridge world, a deterministic gate blocks violations, a human approves.
It works — but it is **one goal, one shot, one domain-pair**.

v3 does three things: make the **harness explicit and generic** (five first-class components, per
[`harness/`](harness/)), make the agent **multi-goal**, and add **Agent Board** — a new 6th repo, a
glanceable dashboard over every running goal.

**North star: an impactful demo.** Scope is cut against demo beats, not against completeness.

## 1. Why now — the three limits v2 hit

1. **The harness is implicit.** [`V2_DESIGN_PROPOSAL.md`](V2_DESIGN_PROPOSAL.md) named 11 harness
   modules; the device's `docs/HARNESSES.md` maps each to a real primitive. But the architecture input
   ([`harness/Family_Hub_Agentic_Harness_Architecture.md`](harness/)) names **five** components that
   should be first-class and identifiable. Of those five, two exist in partial form and **three don't
   exist at all**.
2. **It can't do more than meals.** The cloud's actionability gate is hardcoded to `meal_plan` /
   `guest_dinner` in three places. Every other goal is declined before it reaches the device.
3. **Agent Board is impossible today.** It shows N concurrent long-running goals with progress %, ETA,
   next step and alerts. Nothing computes any of that, the UI holds exactly one goal, the contract has no
   multi-goal frame — and running 3 goals would **corrupt the safety gate** (§4).

## 2. Decisions locked (confirmed)

| Decision | Choice |
|---|---|
| **Planning location** | **Device.** The cloud sends the goal contract only — no task list. |
| **Planner depth** | **Two-altitude**: decompose goal → task DAG, then plan each task as it becomes ready. |
| **Agent Board** | **New repo** (`goal-flow-agent-board-ui`), the 6th code repo. |
| **Genericity proof** | **Structural only** — fridge-specific is fine for v3. No 2nd product pack, no `--pack` loader. |
| **Scope** | New use cases + negative paths + persistence + proactive suggestions, **pruned to demo need**. |
| **Tizen** (2 repos) | **Stay frozen**; one re-sync at the end (M9). |

### Why the cloud sends no plan

The architecture infographic says the cloud "creates the execution plan," but the TDS's own §2 lists
**Goal Planner as device component #1**, and §11's sequence reads *cloud receives request → **device**
Goal Planner decomposes*. Only the §1 vision blurb says otherwise. These are discussion docs, so we treat
the component spec as intent — and the engineering agrees:

- A cloud-authored task list is an **ungrounded guess**. It can't know the thermostat is offline or the
  paneer expires Thursday.
- Two planners means **two sources of truth**, and they will drift.
- It would kill the live grounding tool-call stream — the demo's best moment.

**Cloud owns the goal** (interpretation, memory/constraints, the human, board aggregation).
**Device owns the plan** (decompose, check, execute, monitor). *"LLM plans, code checks"* is unchanged.

The one upgrade: today's planner is a **one-shot flat plan**. For Agent Board's multi-day goals
("Birthday party, 68%, next step: buy decorations"), the device planner gains a **decompose altitude** —
goal → task DAG → per-task planning. That is what makes Task Manager real instead of a status-string
rename. One planner, two altitudes.

## 3. The five components (`Harness/`, zero product strings)

`Modules/` dissolves into a generic `Harness/` core plus `Products/FamilyHub/`. **The invariant that makes
genericity real and reviewable: `Harness/` contains no product literals** — no plugin type names, no
`meal_plan`, no ingredient groups. Everything fridge lives under `Products/FamilyHub/`. Fridge functions
**stay mocked** as SK plugins; "generic" is about the harness, not the world.

```
src/GoalFlow.Device/
  Harness/                     # THE GENERIC CORE
    CapabilityManager/         # [1] discovery + resolution + availability + grounding set
    SafetyPolicyEngine/        # [2] grades A0..AX + declarative rules; SafetyFilter = the SK seam
    PrecheckEngine/            # [3] probes + two gates                       (greenfield)
    TaskManager/               # [4] task DAG, lifecycle, retries, progress   (greenfield, centerpiece)
    ProductApiAdapter/         # [5] IProductApiAdapter — the seam plugins call
    Planner/ Approval/ Grounding/ Clock/ Trace/
  Products/FamilyHub/          # ALL fridge specifics
    Adapter/ Plugins/ Probes/ Observers/ config/{policy,prechecks}.json data/
  Agent/GoalAgent.cs           # slimmed: kernel host + per-goal orchestrator
```

| # | Component | State today | v3 |
|---|---|---|---|
| 1 | **Capability Manager** | `CapabilityRegistry.cs` — discovery only; its `PluginType` switch (`:85`) hardcodes all 10 plugin types, contradicting its own "discovered, not hand-listed" docstring | Adds resolution, availability, and the grounding set. Kills the switch, the 13-function whitelist (`GoalAgent.cs:975`), and the hand-written tool list in `BuildGroundingInstruction`. Descriptors = assembly scan + `[SideEffect]` merged with `config/*.json` |
| 2 | **Safety Policy Engine** | `SafetyFilter.cs` — a genuinely good SK filter seam, but checks are hardcoded C# keyed on `"ShoppingList"`/`"PlaceOrder"` strings, no grades | **Keep the filter seam verbatim**; move each check body to declarative rule *kinds* in `policy.json` (1:1 ports). Add grades + AX + the ratchet + per-goal policy (§4) |
| 3 | **Pre-check Engine** | **Does not exist** | `IPrecheckProbe`/`IPrecheckEngine`, two gates. Deliberately **not** in the SK filter — the filter stays safety-only, and "blocked forever" vs "blocked for now" are different user outcomes |
| 4 | **Task Manager** | **Does not exist.** `TaskStatuses` are string constants; goal state is `GoalAgent._activeGoals` with no progress/retries/subtasks | `TaskState` + `TaskRecord` + `ITaskManager`. Every `Transition` emits `task_update`. **This is what makes Agent Board honest** |
| 5 | **Product API Adapter** | **Does not exist.** Plugins call `MockWorldStore` directly | `IProductApiAdapter` extracted from `MockWorldStore`'s existing surface — turns CODE_GUIDE's promise ("the Tizen port swaps plugin internals, never the agent") into a compile-time seam |

### v2's 11 modules → v3's 5 components

Nothing working is thrown away. The 11 modules were real and stay real; they **reconcile onto** the five.

| v2 module | v3 home | Change |
|---|---|---|
| Capability Registry | `CapabilityManager/` | becomes its discovery half |
| Safety & Policy Filter | `SafetyPolicyEngine/` | SK seam kept; checks become declarative; gains grades |
| Approval / Consent | `Approval/` | reads grades instead of tiers |
| Monitor & Adapt | `TaskManager/` | monitoring *is* task lifecycle; domain switch → `IDomainObserver` |
| Planner | `Planner/` | extracted from GoalAgent; **gains the decompose altitude** |
| Actuator | GoalAgent + `TaskManager/` | gains a precheck gate |
| Context Grounding · Scheduler · Trace | `Grounding/` · `Clock/` · `Trace/` | moved; Trace gains per-goal scopes |
| Goal Interpreter · Memory (cloud) | cloud | the interpreter's domain gate generalizes (§6) |
| — | `PrecheckEngine/`, `TaskManager/`, `ProductApiAdapter/` | **new** |

### Grades unify tiers

Tiers and grades are the same axis — how much consent an action needs — except `adapt`, which is not a
consent level at all but a proposal *origin*.

| Grade | v2 tier | Semantics (behavior unchanged) | Example |
|---|---|---|---|
| A0 | `auto` | executes, logged | `Reminders.Create`, all reads |
| A1 | `light` | rides the batched plan approval | `ShoppingList.Add` |
| A2 | `firm` | never executes before explicit approval | `ShoppingList.PlaceOrder` |
| **AX** | *(none — new)* | **prohibited**: never a proposal target, blocked unconditionally, no approval path exists | `Security.UnlockDoor` |
| — | `adapt` | becomes `origin:"adaptation"`, carrying its effect's grade | |

`[SideEffect]` stays as in-code intrinsic risk and back-compat fallback. **`policy.json` may only make a
grade stricter** — a loosening override fails loudly at load, so a typo can't silently weaken the gate.
AX is enforced twice (never offered as a proposal target; filter blocks before any constraint logic).

## 4. Multi-goal concurrency — three real bugs

`Program.cs:127` already fans every dispatch out via `Task.Run`, so 3 goals **will** run concurrently the
moment the board can submit them. These are live defects, not refactor concerns:

1. **The `SetPolicy` clobber** (`GoalAgent.cs:230`) — `_safety.SetPolicy(...)` on a **singleton**
   `SafetyFilter`. Goal B's dispatch overwrites goal A's hard constraints mid-plan → *the deterministic
   gate enforces the wrong family's allergens.* The worst possible failure for "LLM plans, code checks."
   **Fix:** policy keyed per goal, current goal flowed to the filter via `AsyncLocal<string>`.
   **Must land in M1, before the board can ever submit two goals.**
2. **Trace has one `_seq` and one pinned goal_id** (`Trace.cs:20-21`) — `BeginGoalScope` resets seq and
   re-pins, so goal A's later events stream under B's id and the UI drops them. **Fix:** `BeginGoalScope`
   returns a `TraceScope` owning its seq/ids.
3. **`_activeGoals`/`_pendingPatches` are plain `Dictionary`** (`GoalAgent.cs:49,53`) mutated from
   `Task.Run` threads → torn state. **Fix:** `ConcurrentDictionary` + a per-goal `SemaphoreSlim`.

**Cloud:** `goal_locks: defaultdict(asyncio.Lock)` keyed by `goal_id` around every `start_goal`/
`resume_goal` before the `asyncio.to_thread` hop (the `MemorySaver` thread-safety risk is already flagged
in the cloud's AGENTS.md; 3 goals make it likely).

**Model:** cross-goal parallel for monitoring/adaptation/approval; **device planning capped at 1**
(`SemaphoreSlim(1)`) — queued goals surface as **Waiting** on the board, turning a queue into a visible
state instead of a hidden stall, and keeping token burn sane.

## 5. Persistence

- **Cloud:** `MemorySaver` → `SqliteSaver` (`langgraph-checkpoint-sqlite`, one dep) at `data/goalflow.db`,
  plus stdlib-`sqlite3` `board` + `suggestions` tables in the same file. No Redis, no ORM.
- **Device:** serialize each goal context to `data/goals/<goal_id>.json` on change; reload at startup.
- **Demo value:** kill the cloud mid-demo, restart, the board rehydrates. Also insurance against a crash
  on stage.

## 6. Cloud — generic gate + BoardService

**Actionability gate.** Delete `_canonical_domain` (`nodes.py:121`, a keyword hack that collapses every
domain back to the same two) and the hardcoded domains in the `actionable` field (`:90-108`) and the
interpret prompt (`:281-291`). All three must go, or every new v3 goal is declined before reaching the
device. The good news: the cloud **already caches** the device's capabilities per session
(`server.py:131`) and simply never feeds them to the graph — so this is mostly plumbing. The prompt
becomes *"set actionable=true iff the goal can plausibly be advanced using these advertised functions."*

**AX functions still make a goal actionable.** The cloud answers *"is this in the product's world?"*; the
device Safety Policy Engine answers *"may it happen?"* and produces a far better refusal. That distinction
is exactly what the "unlock the door" beat demonstrates. **Must land before M7.**

**BoardService** (`src/goalflow_cloud/board.py`, ~250 lines, deterministic, unit-testable). Board truth is
**cloud-derived** from frames the hub already routes, folded against device `task_update` events:

| Field | Source |
|---|---|
| `progress_pct` | completed tasks / total tasks (from the DAG) |
| `next_step` | `NextReady` task title; unanswered adaptation wins; `awaiting_approval` → "Review & approve" |
| `eta` | `time_window.end` (UI renders "2 days" by date-diff) |
| `pending_tasks` | tasks not Completed + approval-required proposals not executed |
| `alerts` | open adaptations + safety blocks + precheck failures + device offline |
| `state` | `completed` / `waiting` / `at_risk` / `on_track` |

## 7. Contract v3 (additive)

Canonical `CONTRACT.md` stays in the cloud repo. Any frame change touches **all** mirrors in one pass:
`CONTRACT.md`, `contract.py`, both `contract.ts` (chat UI + board), `Contracts/*.cs` — **and
`ws.ts INBOUND_TYPES`** (`ws.ts:28`), an allowlist that *silently drops* unlisted frames.

- `plan_ready.payload.precheck`; `task_id` on `plan[]`/`proposals[]`
- `proposals[].grade` (A0|A1|A2) alongside kept `tier`; adaptations gain `origin:"adaptation"`
- `capabilities`: per-function `grade` + `prechecks`; steering list renamed to the v3 components
- new agent_event `task_update {task_id, state, detail}`; `status.executed[].result` gains
  `"deferred_precheck"`
- **board frames:** `board_snapshot` / `board_update` / `board_get` / `goal_state_get` / `goal_accepted`;
  `user_goal` gains `client_ref`
- **suggestions:** `signals` (device→cloud) + `suggestion_action` (ui→cloud)

`GoalSummary` = `{goal_id, client_ref, title, subtitle, domain, state, task_status, progress_pct,
next_step, eta, pending_tasks, alerts{count,severity}, activity[], updated_at}`. Deltas are **whole
GoalSummary objects** (replace-by-id, idempotent). `board_seq` is monotonic per session; a gap → the UI
sends `board_get` to heal. `client_ref` exists because with 2 goals in flight the UI cannot otherwise tie
an inbound `goal_id` to which submission it was.

## 8. Agent Board — new repo `goal-flow-agent-board-ui`

### How it talks to the device: it doesn't

The board never touches the device — that would break the contract's hub-only invariant.
It is a **read-mostly projection** of state the cloud derives:

```
DEVICE                    CLOUD (hub)                    BOARD UI
  │  task_update ──────────►│                              │
  │  plan_ready  ──────────►│  BoardService folds every    │
  │  status      ──────────►│  frame it already routes     │
  │  proposal    ──────────►│  into a GoalSummary          │
  │                         │──── board_snapshot ────────► │  on bind
  │                         │──── board_update ──────────► │  per change
  │                         │◄─── board_get ────────────── │  heal a seq gap
  │  ◄──── dispatch ────────│◄─── user_goal ───────────── │  New Goal
```

This is why `task_update` had to land before the board: the task DAG lives on the DEVICE
(only it can ground a decomposition), so the cloud could not compute "68%, next step: buy
decorations" until the device started saying so. The device is *upstream* of the board,
never a peer. The board doesn't need the device online to render, either — summaries
persist (M5).

**The board SENDS only:** `hello`, `select_device`, `board_get`, `goal_state_get`,
`user_goal`, `suggestion_action` (M8). **Never `approval` or `control`.**

**Approvals live in the chat UI (decided).** The board shows `Waiting` + a pending count;
tapping the card drills through. Keeping the board read-mostly is what makes it glanceable,
and the chat UI's proposal cards — with tier, the literal `module.function`, and the money
warning — already exist and work. Approving is two taps; a glanceable surface should tell
you something needs you, not be where consequential decisions are made in one tap.

**Drill-in is cross-app (decided).** The board and chat UI are two separate Vite apps on
two ports, so the card links to the chat app's origin with `?goal=<id>`, read from
`VITE_CHAT_UI_URL` and defaulting to `window.location.hostname:5173` — the same
derive-from-the-page-host trick `ws.ts` already uses so a tablet on the LAN works with no
config. It is honest about them being two surfaces; on a real Family Hub this would be a
deep link into the Hub's own app instead.

React 18 + Vite 5 + TS, matching the chat UI's stack (no component library, no Tailwind, hand-written
tokens). **Light theme**, per the mock; the chat UI stays dark. Copy-don't-share `lib/ws.ts` (the
singleton-socket pattern, the 1012-eviction rule, `?device=` + localStorage self-heal pairing) and
`types/contract.ts`.

State is a **keyed collection from day one** — `{goals: Record<id, GoalSummary>, goalOrder, boardSeq,
suggestions}` — driven by `board_snapshot`/`board_update`, not by per-goal frames. Drill-in: a card opens
`/?goal=<id>` in the chat UI → `goal_state_get` rehydrates plan + status. The dark "watch it think" stage
is v2's strongest asset and becomes the **detail view**; board (glanceable widget) → chat UI (theater)
reads as deliberate. Bottom nav renders Home/Food/SmartThings/Entertainment as inert chrome.

## 9. Use cases (pruned to demo need)

The board must show **3+ concurrent goals in different statuses**. The lineup mirrors the mock so
reviewers recognize it instantly — and each goal is the hero demo for a different component:

| Goal | Board state | Proves | Needs |
|---|---|---|---|
| **Weekly Meal Plan** | On Track 43% | *regression canary* — must run unchanged after the refactor | exists |
| **Birthday Party Prep** | On Track 68% | **Task Manager** (DAG, progress, ETA, next step, alerts) | FamilyBoard plugin; the 3 stubs implemented |
| **Vacation Prep** | At Risk 25% | **Pre-check Engine** + **AX** + retry | SmartThings, Security plugins |
| **Grocery Restock** | Waiting | **Safety Policy Engine** (budget cap) + A2 | Budget plugin, prices |

**3 new plugins** (SmartThings — folds in scenes/thermostat/energy/vacuum; Security; FamilyBoard) plus
implementing the 3 existing named stubs (Budget, Notify, FamilyProfiles). **Cut** vs. the long catalog:
no Vision/fridge-scan (Vacation's thermostat-offline beat proves prechecks identically), no separate
Energy plugin, no Media/Gallery/Display — Movie Night is the best cross-domain proof, saved for v3.1.

**Negative paths** — cheap once the plugins exist, and they prove the harness better than happy paths:

- **AX** — "unlock the back door for the plant sitter," *inside an otherwise successful* Vacation plan.
  The planner finds `Security.UnlockDoor` in its toolbox, the engine refuses, that one step ships blocked
  with an alternative. Proves *actionability ≠ permissibility*.
- **Pre-check failure** — thermostat offline → that subtask goes At Risk while others proceed → fire
  `thermostat-online` → it resumes automatically.
- **Safety block with recovery** — a cart at ₹1,850 is blocked → the model *visibly re-plans* a cheaper
  cart → ₹1,420 → A2 approval. A block is a conversation with the planner, not a dead end.
- **Child authority** — same goal text, two profiles, two outcomes. New `constraints.hard.actor`
  `{member, role, max_grade}` + one generic `actor_authority` rule. Authority as data, not code branches.
- **Retry** — vacuum offline → precheck fail → retries with backoff, counter visible in the trace.

**Proactive suggestions.** The device emits deterministic `signals` (inventory low, expiring soon — from
existing Inventory reads) on connect and after world mutations; the cloud folds them into suggestion cards
by rule; tapping **+** synthesizes a `user_goal` through the *normal* pipeline (understanding gate and
all). No unprompted LLM calls. Beat: execute a shopping approval in goal A → a suggestion appears → tap
**+** → a 4th goal spins up. Proactivity emerging from agent activity.

All mock-world additions stay **offset-relative** — the no-absolute-dates invariant holds.

## 10. Roadmap (M0–M9)

Demo runnable after every milestone. **Confirm before phase jumps.**

- **Phase A — device harness.** M0 restructure + seams, *zero behavior change* · M1 Safety Policy Engine
  (**includes the `SetPolicy` fix**) · M2 Task Manager + two-altitude planner · M3 Pre-check Engine.
- **Phase B — multi-goal + cloud.** M4 generic actionability gate (before M7) · M5 concurrency +
  persistence.
- **Phase C — Agent Board.** M6 contract-v3 board frames + `BoardService` + `goal-flow-agent-board-ui` +
  chat-UI `?goal=` deep-link. *Parallelizable with Phase B.*
- **Phase D — demo.** M7 plugins + use cases · M8 negative paths + proactive suggestions · M9 Tizen
  re-sync (one pass), device `HARNESSES.md` v3 rewrite, demo choreography.

**Cut order if short:** child-authority → suggestions → device persistence → retry.
**Never cut:** M0 restructure, M1 policy engine, M2 Task Manager — those three *are* the five folders and
the board's honesty.

## 11. Risks

1. **The `SetPolicy` clobber is a live safety bug**, not a refactor concern — land it in M1.
2. **Prompt regressions** from config-driven prompts. Domain fragments start as **verbatim** copies of
   today's text; diff sim outputs before any wording change.
3. **Tizen sync debt** — the byte-copy recipe names `Modules/`, which disappears in M0. One re-sync at M9;
   mechanical, but must not be forgotten.
4. **Two-altitude planner cost/latency** — decompose adds an LLM call per goal. Cap task count, validate
   the DAG in code, **fail soft to a single synthesized task** (= today's behavior).
5. **Scope creep toward the 13-component TDS** — resist. The extra components map onto existing modules.
   No empty folders.

## 12. Amendments from M0 (2026-07-17)

M0 shipped and corrected three things this doc got wrong. Recorded here rather than
quietly fixed, because each was an idea that sounded right and did not survive contact.

1. **§12's "sim output byte-identical" was unsatisfiable.** `--simulate-week` makes ~10
   OpenRouter calls at temperature 0.1–0.2; its text differs every run. The real gate is
   the deterministic surface — the `capabilities` frame and the derived grounding list,
   diffed against goldens captured *before* the refactor (`verify/m0/`), with the sims
   asserted **structurally** (7 days, `safety.gate == passed`, proposals from the known
   set). Corrected below.
2. **`data/` does not move to `Products/FamilyHub/data/`.** `--data ./data-a` is a
   documented multi-session workflow and `EnsureDataDir` seeds from a hardcoded `"data"`,
   so moving it changes CLI behavior — the one thing M0 forbids. Tizen reinforces this:
   its resource dir is read-only, so the runtime data dir is a deployment concern, never
   source-tree-relative. Read §3's intent as *the **seed** is product-owned* and defer.
3. **"`Harness/` contains zero product strings" is false on day one, by this doc's own
   sequencing** — it defers the `IDomainObserver` extraction to M2 and `policy.json` to
   M1, so those literals are *supposed* to survive M0. The honest invariant is **"no NEW
   product strings; existing ones pinned and scheduled"**, enforced by a count that can
   only shrink (10 at M0: 6 in SafetyFilter → M1, 4 in MonitorAdapt → M2). Every one
   carries a `// PRODUCT-DEBT(Mx)` marker.

Two facts M0 established that later milestones depend on:

- **The grounding set is 13 = the reads of the 7 *implemented* plugins.** A naive "all
  non-side-effecting functions" rule yields **17** — `FamilyProfiles` and `Budget` are
  reads that merely throw. Availability (`[Unavailable]`) is load-bearing, not polish;
  verified by stripping it and counting.
- **Order is part of the contract with the model.** The grounding set is in declaration
  order while the capabilities frame sorts alphabetically. The tools array is the prompt,
  so `FamilyHubProduct`'s descriptor order is behavior, not style.

## 12b. Amendments from M1 (2026-07-17)

M1 shipped the Safety Policy Engine. Three things worth recording:

1. **The `SetPolicy` clobber had a twin, and the twin was worse.** §4 named the
   plan-path clobber. Implementing it turned up that `ApplyApprovalCoreAsync` armed
   **no policy at all** — it called `SetTrace` but never `SetPolicy`, then invoked
   approved proposals through the kernel. So the *actuation* gate, the last check
   before money moves or an appliance starts, ran against whatever policy the last
   plan run left behind. One goal → right policy by luck. Both are fixed by the same
   per-goal scoping; all three entry points now enter their goal's scope, and an
   unscoped call logs `safety_unscoped` rather than inheriting a stranger's policy.
2. **Allergen matching was a literal substring test** — `allergens:["peanuts"]` did
   not block `"peanut butter"`. Latent (the meal contract seeds no allergens; no
   recipe contains nuts) but live the moment a goal proposes free-text groceries for
   an allergic family, i.e. the birthday/nut-allergy case in §9. Fixed in M1's
   `blocked_terms` rule with token/stem matching. The over-blocking direction is
   guarded just as hard: a "nuts" allergy must still allow coconut, butternut squash
   and nutmeg, or the family switches the agent off.
3. **Gate 3 counted comments as debt.** After moving the checks into `policy.json`
   the count hadn't moved — the coupling was gone but doc comments explaining
   *"this used to hardcode ShoppingList"* still matched. As written it priced honest
   comments as debt and rewarded deleting them. It now strips comments and measures
   dependency. Harness debt: **10 → 4** (all `MonitorAdapt`, → M2).

`adapt` turned out **not to be a grade at all** — it says where a proposal came from,
not how much consent it needs. It becomes a proposal *origin*; an adaptation carries
the grade of the effect it performs. Mapping it onto the A0–AX axis would have baked a
category error into an enum.

## 12c. Amendments from M2 (2026-07-17)

M2 shipped the Task Manager and the decompose altitude. Four things to record:

1. **Gate 3 had been under-counting badly: 4 was really 52.** Its vocabulary was
   capitalized *module* names, so it never saw that `MonitorAdapt` knew the product's
   whole **data model** — which documents exist (`calendar`, `daily_events`), their
   shapes (`guests.pending_updates`), a hardcoded 17:30–18:30 prep window, guest copy,
   and a materiality table made of this product's change kinds. So §3's "Harness/ is
   clean" claim was true for CapabilityManager / SafetyPolicyEngine / ProductApiAdapter
   and **false for MonitorAdapt**, on a number that implied otherwise. Now
   case-insensitive and covering domains, modules, resource names and change kinds.
   After the extraction: **52 → 6**, and the 6 are one prompt line in `Grounding.cs`.
2. **Materiality moved to the observers, against this doc's "MaterialityPolicy stays
   unchanged".** Its rules *are* product vocabulary — only the domain knows a nut
   allergy matters and a restocked pantry item nobody cooks with does not. The harness
   keeps the guarantee (material only, exactly once, one scoped re-plan); the product
   owns the judgement. `IDomainObserver` is the seam. This doesn't weaken "LLM plans,
   code checks": an observer is deterministic code, never a model.
3. **Progress is a step function for the meal week, and that is honest.** §4 assumed
   `progress = completed tasks / total`. True — but the meal week decomposes into
   *planning* steps that all finish at the same approval, so it reads 0% then 100%.
   The board's "68% · next step: buy decorations · 3 pending" assumes tasks that are
   multi-day **work** (order the cake, send invites) completing one at a time — the
   birthday-party shape (§9), not the meal-week shape. Same formula, different goal:
   a meal week is planned once and then merely happens. Progress therefore counts
   work the agent has done (Completed **or Monitoring**); a Failed task is terminal
   but never progress, so a stuck goal can't drift toward 100%.
4. **A goal needs an end condition.** Nothing completed a monitored goal, so it would
   monitor forever and the board would show a finished week stuck "in progress". It
   completes when the contract's `time_window` closes, read against the generic clock
   — the calendar decides, not the agent.

The decompose altitude works and produces the shape the input docs describe: *identify
expiring inventory → find recipes using them → select one per weekday, accounting for
Wednesday sports → shopping list under $60 → validate budget → add to calendar → set
reminders*. Constraints honoured from the contract, no world facts invented. Guest
dinner decomposes to 6–8. **Fail-soft verified by breaking it**: garbage from the
decompose call falls back to one task and still plans a full 7-dinner week.

## 12d. Amendments from M3 (2026-07-17)

M3 shipped the Pre-check Engine. **All five components now exist.**

The design already said prechecks stay out of the SK filter; implementing it showed
*why* that matters more than it first appears. The three gates answer three different
questions, and the difference is one the **user feels**:

| gate | question | answer means |
|---|---|---|
| Safety Policy Engine | is this ALLOWED? | never — the house rules forbid it |
| Approval | is this CONSENTED? | waiting on a person |
| **Pre-check** | is this POSSIBLE? | **not yet** — something is unplugged; it will resume |

Conflating the first and third would teach the model to re-plan *around* a temporary
outage as though it were forbidden — dropping the oven step rather than waiting for the
oven — and would tell the user their house rules blocked something when actually a
device was offline. Hence `PrecheckVerdict` is a separate field from `SafetyVerdict` on
`plan_ready`, and the remediation text is the deliverable: *"the oven is offline —
reconnect it and this will resume"* tells someone what to DO.

Two corrections to §3's sketch:

1. **`device_state.json` lives in `data/`, not `Products/FamilyHub/data/`** — per M0's
   own amendment (data is the mutable runtime world; only `config/` is product-adjacent
   and ships with the binary). I contradicted that while writing it and caught it.
2. **Gate 2 matters more than gate 1**, which the design underplayed. Conditions drift
   between planning and approval — and approval is *precisely* where the delay is,
   because it waits on a human. An oven online at plan time can be unplugged by the time
   someone taps Approve.

`deferred_precheck` is **not a failure and not a drop**: `MarkExecuted` is deliberately
not called, so the approval stands and the effect executes when the world recovers.
Verified by contrast — with the oven offline, apply *and* replay both defer; with it
online, apply executes and replay reports `already_executed`. (Recovery *across a
restart* additionally needs the ledger to persist — M5.)

Verified end-to-end: signed out → the goal returns 0 plan items with an actionable
reason and **zero LLM calls** (checked before a token is spent); oven unplugged between
planning and approval → that one proposal defers while the others proceed. Gate 9
falsification-tested: a stubbed always-pass probe trips 4 of its assertions.

## 12e. Amendments from M4 (2026-07-17)

M4 made the actionability gate generic. §6 called this "mostly plumbing" — the hub had
cached the device's capabilities since v2 and never fed them to the graph. That part was
right. What it missed nearly shipped a regression.

**Deleting `_canonical_domain` broke guest routing.** §6 said to delete the keyword hack,
and it *was* a hack — but it was load-bearing in a way nothing recorded. The device
**routes on the domain string**: `IDomainObserver` answers to it by name. With the hack
gone the interpreter invented plausible slugs, and a guest dinner labelled `meal_plan`
silently lost its RSVP watching — the guest demo's entire beat, failing quietly with no
error anywhere. Caught only because the gate asserts the *domain*, not just actionability.

Fixed the right way rather than by restoring the hack: **the device advertises its
domains** (`capabilities.domains[{id, hint}]`, derived from its registered observers — add
an observer and the cloud learns the domain exists), and the interpreter prefers them,
coining a new slug only when none fits. That is what §4 of the capability-pack design
called for; it just wasn't connected to the gate.

Two smaller decisions:

- **No device → decline, don't guess.** Guessing what we can do is precisely how this got
  hardcoded to two domains in the first place.
- **The refusal describes THIS device.** The redirect used to promise "the week's meals or
  help you host a dinner" from a literal — which becomes a lie the moment a plugin is
  added, the assistant claiming it can't do something it just learned. It now reads the
  modules' own human-written descriptions.

**A contract change landed here, not in M6**: `capabilities.domains`. Gate 1 caught it and
forced a deliberate re-baseline rather than an accidental one — which is exactly its job.
The grounding set is untouched at 13. §7's "all mirrors move in M6" still holds for the
board frames; this one had to land with the gate that needs it.

Verified live: `meal_plan` and `guest_dinner` both route correctly (and the nut-free
adaptation fires end-to-end); "get the house ready, we're away next week" is now
actionable where v2 declined it; trivia and poems are still declined — generic must not
mean "accepts anything".

## 12f. Amendments from M5 (2026-07-17)

M5 closed the concurrency and persistence gaps. **Phase B is done.** §4's three bugs are
all fixed (the `SetPolicy` clobber in M1, the `Dictionary`s in M2/M5, Trace here), and
§5's persistence landed.

**The two cloud fixes hold each other up**, which §5 treated as separate items.
`check_same_thread=False` on the SQLite checkpointer is only safe *because* the hub now
holds a per-goal lock around every invoke: a `thread_id` is a `goal_id`, so two threads
never touch the same checkpoint. Shipping the checkpointer without the locks would have
swapped a lost-state bug for a corrupted-state one.

**Why the locks are per-goal and not global:** goals must still run in parallel — goal B's
interpretation must not wait on goal A's approval. Per-goal serialised, cross-goal
concurrent. All five invoke sites audited, not assumed.

**Planning is serialised behind one slot** — and that is honesty, not correctness (state is
per-goal now). Three concurrent plans mean triple the token burn on a key that already
402s, and a "watch it think" stream interleaved from three goals reads as noise. A queued
goal emits `phase: "queued"` and says so, which the board shows as **Waiting** — a state a
person can read, rather than a card sitting there. Short work (approvals, control ticks,
adaptations) does *not* take the slot; blocking those behind someone else's 60-second plan
would be the very stall this avoids.

**A testing lesson, now twice over.** Gate 11 passed against a deliberately shared Trace
scope. The barrier was one `TaskCompletionSource`, and `await` on an already-completed task
continues **synchronously** — so goal-a ran to completion before goal-b started, the two
never overlapped, and the bug sailed through. Same shape as M2, where the DAG was declared
in dependency order and a broken `NextReady` still looked correct. **A concurrency test
that does not actually interleave is theatre.** Fixed with a two-way rendezvous; the same
falsification then reported goal-a: 0 frames, goal-b: 20 — every one of A's events stolen.

Gate 12 tests the promise rather than the library: run a goal to its interrupt, **throw the
graph away**, build a new one over the same file, and *resume*. Reading state back is not
enough — the interrupt has to still be there to answer. Falsified against `MemorySaver`,
which reports exactly the v2 failure: *"a NEW graph sees nothing"*, *"the goal is unusable,
just visible"*.

## 12g. Amendments from M6 (2026-07-17)

M6 built `goal-flow-agent-board-ui` and the cloud fold behind it. **Phase C has begun.**
The board renders live against a real device: a goal submitted on the board reaches the
card, the card links into the chat UI, and confirming there moves the card within ~3s.

**The card is born at the understanding gate, not at dispatch.** §8 had `on_goal_created`
firing when the contract goes to the device. But the cloud holds every goal at the
confirm-understanding interrupt *first*, and that gate can hold it indefinitely — it is
waiting on a person. So the one state where a human is the blocker was the one state the
board could not show: a goal started from the board sat on its optimistic placeholder
forever, with nothing anywhere saying it wanted you. `on_understanding` now creates the
card (`next_step: "Confirm what the agent understood"`, one `warn` alert), and
`on_goal_created` overwrites it — **confirming IS the resolution**, so the alert clears
itself with no extra event. `goal_state_get` replays the cached understanding, without
which the board's own drill-in link landed on an empty stage.

**A plan's rationale is not activity.** §8 fed `plan_ready.explanation` into the card's
activity line. That field is a paragraph, and clipped to fit it rendered *"The 7-day
vegetarian dinner plan leverages existing inven…"* — the exact failure `_title` was
written to prevent, reintroduced one field over. Activity now comes from **completed task
titles**, which the planner already writes as short human phrases. Before the first task
finishes the line is empty, which is honest: nothing has happened yet.

**Gate 13 passed while the bug shipped**, because its fixture explanation was a tidy
one-liner. *A fixture prettier than production tests nothing.* The gate now feeds the
field a real paragraph. This is the same lesson as M2 and M5 in a third costume: the M2
DAG was declared in dependency order, M5's barrier never interleaved, and M6's fixture was
too neat — **every one of them made the gate incapable of failing.**

**One wire, two spellings.** The device emitted `task_update.state` via
`ToString().ToLowerInvariant()` → `"awaitingapproval"`, while `task_status` and `phase`
carried `"awaiting_approval"`. It hid because `AwaitingApproval` is the *only* multi-word
member of `TaskState` — every other value round-tripped by accident, and the cloud's check
happened to test `"completed"`, a single word. Fixed with `Trace.ToWire()`; the
enumeration is now written into `CONTRACT.md` (**an example does not pin an enum**), and
gate 14 grew a field-level check — it had only ever compared frame `type`s and
agent_event kinds, so any field's own enum could drift freely.

**Gate 14 must know the two UIs are different shapes.** Applied uniformly it demanded the
board mirror `approval`, `control`, `dispatch`, `plan_ready`. The board is a deliberate
slice, so the gate now carries a per-UI spec — and `types_exempt` for the board *is* the
"read-mostly" decision written down: adding `approval` to its mirror fails the build and
asks for the decision to be changed on purpose. It also now checks the board's own
`INBOUND_TYPES`, which was unchecked — the newest silent dropper in the system, exactly
the hole this gate exists to close.

**Design-mock fidelity is a reading decision, not a pixel one.** The mock's four footer
cells wrap to two lines; ours ellipsed, rendering *"Fetch curre…"* — destroying the single
most useful fact on the card. And four equal columns is a layout convenience, not a
reading one: Next Step is a sentence fragment, the other three are a date and two
integers, so it takes 1.7fr.

**The device's LLM calls had no timeout — and the board is what made it visible.**
Observed live, twice in one session: a streaming call to `openai/gpt-oss-120b` stopped
mid-token and never returned. The provider was healthy (a direct request answered in
1.5s — OpenRouter had simply routed that stream to one that hung), the device process
stayed alive, nothing was logged, and the card read *"Working out the steps…"* for **four
hours**. A goal could stall forever while every surface reported progress. The board did
not cause this; it made a pre-existing hole legible, which is the argument for building
it. Fixed here rather than deferred to M8 — it was reproducible enough to hit twice and
it is a demo-killer.

`HttpClient.Timeout` does **not** cover it: streaming reads with `ResponseHeadersRead`,
so the timeout is satisfied the moment headers arrive and everything after is an
unbounded read. The deadline has to be a cancellation token. It is *linked* to the
goal's token and never cancels it, so `IsTransientProviderError` already classifies the
expiry as transient — **a hang flows into the retry machinery that was already there for
provider flakiness**, instead of needing a second path.

**Gate 15 passed on its first run, and was worthless.** Its fake SSE server emitted a
token containing an unescaped quote, so the chunk was invalid JSON; the SDK threw
`JsonReaderException` in 87ms; `JsonException` is *itself* in the transient list — so
every assertion went green with the deadline never firing. Two things fixed it: a fixture
the client actually parses, and a **lower** time bound (`>= 2.5s`), which nothing but
waiting out the deadline can satisfy. **This is the fourth gate in this project to pass
while being incapable of failing** (M0's `&&`, M2's ordered DAG, M5's synchronous
barrier, M6's pretty fixture). The pattern is always the same: the test never reaches the
state it claims to test.

Gate 16 is separate on purpose: gate 15 proves the *mechanism*, gate 16 greps that every
call site is *wired* to it. Different claims — the mechanism working while one call site
sits on the bare token is exactly how this regresses silently. And `timeout 120` in the
gate script is load-bearing: without the deadline the verification **hangs**, and a gate
that hangs on regression is barely better than one that passes.

## 12h. Amendments from M7 (2026-07-17)

M7 added the Vacation and Birthday use cases and the plugins behind them. **Both run
live against a real device**: the vacation goal routes to `vacation_prep` and plans
lock-and-arm + eco appliances + reminders; the birthday goal routes to `birthday_party`
and costs the order at $24.50 under the $120 cap via the new Budget plugin.

**A use case turned out to be almost nothing but an observer.** The M4 genericity work
paid off exactly as designed: the cloud needed **zero** changes. An `IDomainObserver`
IS the domain advertisement, so registering `VacationPrepObserver` /
`BirthdayPartyObserver` is what makes the cloud interpreter route to those domains —
no interpreter edit, no gate edit, no contract field. The whole cloud-side cost of two
new use cases was deleting stale documentation.

**`vacation_prep` is the M4 gate's payoff made real.** v2's interpreter *declined* "get
the house ready, we're away next week" as out of scope. It is now actionable purely
because the device advertises Security + Appliance + Reminders + Calendar — "what this
assistant can do is a fact about the device that is plugged in." The generic gate wasn't
a refactor; it was the thing that let a use case be added without touching the cloud.

**Implementing a stub is deleting one line.** The three stubs (FamilyProfiles, Budget,
Notify) already sat in the manifest with constructors wired; each became real by writing
the method bodies and deleting its `[Unavailable]` attribute. That grew the planner's
grounding set 13 → 18, which gates 1–2 byte-diff — and the golden diff **is** the
reviewable record of the catalog change, not a failure. The stub-exclusion mechanism
stays load-bearing for anything still unimplemented.

**Old foresight got used.** Security's `ArmSecurity` binds the `camera_operational` and
`ai_vision_initialized` prechecks — two probes that shipped in `device_state.json` back
in M3 and sat unused ever since, waiting for exactly this. A goal now can't tell a
departing family the house is watched when the camera is dark.

**The gate-that-can't-fail returned in a fifth costume.** Gate 17 was written
`head -1 dump | python3 - <<'PY'` — but `python3 - <<'PY'` binds stdin to the heredoc
(the script itself), so `json.load(sys.stdin)` read an empty stream: the gate would have
**crashed with JSONDecodeError**, not asserted anything. Same lesson as M0's `&&`, M2's
ordered DAG, M5's synchronous barrier, and M6's pretty fixture — the check never reached
the state it claimed to test. Caught by falsifying it (drop a domain, drop a plugin);
fixed to read the frame from a file.

**One chat-UI robustness fix:** `reduceInbound` had no `default` case, so an unmapped
frame returned `undefined` and the next frame crashed reading `state.nextId`. Every
allowlisted type is handled today, so it never fired in production — but a reducer that
can return undefined is a loaded gun the moment the contract grows. Now defaults to
carrying the goal update and dropping the frame.

**Scope held.** The chosen cut was Vacation + Birthday done well, NOT the mock's full
SmartThings/FamilyBoard plugin roster — ApplianceControl is already SmartThings-backed
and Notify.Announce already covers a family board, so those would have been plumbing
without new demo capability. The LLM uses what a goal needs (Budget featured in both
plans; Notify/FamilyProfiles are present and proposable but unused this run) — the
capability existing is the deliverable, not the LLM being forced to call it.

## 13. Verification

- **Run the LATEST milestone's gate** in the device repo — `verify/m1/check.sh` today; each chains the
  previous, so the earlier gates stay permanent regression checks rather than milestone trivia. (No test
  framework exists there; none was added.) All gates are offline and need no API key; `--smoke` adds the
  LLM sims.
- **Regression canary, every milestone:** `--simulate-week` + `--simulate-guest` still produce a
  well-shaped plan (7 days, safety passed, known proposal targets) — **not** byte-identical; see §12.
  The meal plan working unchanged after the refactor *is* the test that the harness didn't get less generic.
- **M0 gate (shipped):** the `capabilities` frame byte-identical to a pre-refactor golden, and the derived
  grounding set == the 13 functions **in the same order**.
- **Gates must be falsification-tested.** A gate that cannot fail is a false assurance — M0's first
  version silently passed a deliberately broken build (`diff && echo PASS` swallows failure under
  `set -e`). Break it on purpose before trusting it.
- **Concurrency:** submit 3 goals with *different* hard constraints; assert each goal's blocks cite its
  own constraints (the `SetPolicy` regression) and that no `agent_event` seq collides across goals.
- **Persistence:** kill the cloud at `awaiting_approval`; restart; the board rehydrates and approval resumes.
- **Safety ratchet:** a `policy.json` entry loosening A2→A1 fails loudly at load.
- **End-to-end (browser):** cloud + device + chat UI + board. Board counts match goal states; fire
  `thermostat-fault` → Vacation flips At Risk; approve the restock → Waiting → On Track.

---

*Input docs: [`harness/`](harness/) — the architecture discussion + TDS + the Agent Board and execution-
framework mocks. Prior architecture: [`V2_DESIGN_PROPOSAL.md`](V2_DESIGN_PROPOSAL.md).*
