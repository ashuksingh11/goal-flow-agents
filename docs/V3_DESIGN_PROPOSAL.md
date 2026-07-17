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
| **Agent Board** | **New repo** (`goal-flow-agent-board`), the 6th code repo. |
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

## 8. Agent Board — new repo `goal-flow-agent-board`

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
- **Phase C — Agent Board.** M6 contract-v3 board frames + `BoardService` + `goal-flow-agent-board` +
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

## 12. Verification

- **Regression canary, every milestone:** `--simulate-week` + `--simulate-guest` byte-identical. The meal
  plan working unchanged after the refactor *is* the test that the harness didn't get less generic.
- **M0 gate:** the derived grounding set == today's 13 functions, exactly.
- **Concurrency:** submit 3 goals with *different* hard constraints; assert each goal's blocks cite its
  own constraints (the `SetPolicy` regression) and that no `agent_event` seq collides across goals.
- **Persistence:** kill the cloud at `awaiting_approval`; restart; the board rehydrates and approval resumes.
- **Safety ratchet:** a `policy.json` entry loosening A2→A1 fails loudly at load.
- **End-to-end (browser):** cloud + device + chat UI + board. Board counts match goal states; fire
  `thermostat-fault` → Vacation flips At Risk; approve the restock → Waiting → On Track.

---

*Input docs: [`harness/`](harness/) — the architecture discussion + TDS + the Agent Board and execution-
framework mocks. Prior architecture: [`V2_DESIGN_PROPOSAL.md`](V2_DESIGN_PROPOSAL.md).*
