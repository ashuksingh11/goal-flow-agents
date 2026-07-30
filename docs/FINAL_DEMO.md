# GoalFlow — Final Demo Run-Sheet

The end-to-end demo script for the **general goal-based agent** on a Samsung Family Hub.

> **Thesis (say it once up front):** *one general agent + a pluggable Family-Hub product
> pack.* The LLM **plans**; **code checks** — a deterministic safety filter, a pre-check
> engine, a real task ledger; the human approves; and the agent keeps adapting as the world
> changes. The harness is five generic components; the fridge is a swappable product pack
> behind one interface.

> **The two surfaces (say it once):** *Chat = create. Board = live.* You speak a goal into
> Bixby, the chat surface shows what it understood and what it plans, you sign off — and
> from then on the goal LIVES on the Agent Board.

> **v7 — two goals, and the moment one changes the other.** Three acts and a closer: create
> a meal week; let a day pass and watch it adapt; then create a home-away goal whose
> approval **rewrites the meal week without asking**. It ends on a goal the Hub refuses,
> because knowing what it will not do is part of trusting what it will.

---

## 0. One-time setup

**Five processes** — two services and three web UIs (`~/ashu/git/`). Put your OpenRouter key
in the two `.env` files and use a **paid** model (free `:free` models are rate-limited):

```bash
# goal-flow-cloud-agent/.env  and  goal-flow-device-agent-ubuntu/.env:
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-oss-120b     # a real tool-calling model
```

First-time-only install (once per repo): `.venv` + `pip install -e .` for the cloud;
`npm install` for each UI.

### Run — all on one machine (the standard demo)

Five terminals. **These are the canonical commands.**

```bash
# 1) cloud hub — binds 0.0.0.0:8000 and loads .env
cd goal-flow-cloud-agent && source .venv/bin/activate && ./run.sh
# 2) device agent — dials the cloud (bare --connect defaults to ws://localhost:8000/ws).
#    Run against a SCRATCH world dir so the repo's ./data seed stays pristine and no
#    stale mock-world state carries between runs. `rm -rf` first = a clean world each time;
#    the dir self-seeds from ./data on first use. (data-*/ is gitignored.)
cd goal-flow-device-agent-ubuntu && rm -rf data-run1 && \
  dotnet run --project GoalFlow.Device.csproj -- --connect --data ./data-run1
# 3) Agent Board — where a goal LIVES
cd goal-flow-agent-board-ui && npm run dev
# 4) chat UI — where a goal's CREATION is WATCHED (understanding card, working column)
cd goal-flow-agent-chat-ui && npm run dev
# 5) Bixby surrogate — where you SAY the goal (v4.1: the chat surface has no composer)
cd goal-flow-agent-bixby-ui && npm run dev
```

> **What the chat surface looks like now.** One **working column**: engines that have finished
> collapse into receipts carrying their verdict and their real duration
> (`Grounding · grounded · 59.3s`), the engine that is running holds a single focus card with the
> live reasoning transcript and its tool calls inside it, and the ones still to come sit below as
> ghosts. The plan lands underneath, one row at a time, into slots reserved before the content
> arrives. Every card sizes to its own content — nothing is squeezed, and only the content area
> scrolls while the goal itself stays pinned at the top. The phase rail is gone (it was a second
> progress indicator for the same run). See [DESIGN.md](DESIGN.md) §7.

> **Ports are assigned in START ORDER from 5173** — Vite takes the next free one, so read
> each terminal's printed URL rather than trusting the numbers here.

Open **three tabs**, at whatever URLs the three Vite terminals printed: the **Bixby
surrogate** (you type every prompt here), the **chat UI** (you watch a goal being created and
approve its plan) and the **Agent Board** (goals live here). On the real Hub the shell swaps
between them — chat full-screen while you create, then the board full-screen for the rest; in
the browser demo you switch tabs by hand at the hand-off. The chat and board headers show
**● open** when connected.

Dates are **relative to the real today** — the sim clock and plan dates just work.

### Run — across machines (cloud on Ubuntu, board on a tablet, device on the Tizen Hub)

Same commands, only endpoints change (both UIs derive the hub from whatever host served
them):

- **Cloud (Ubuntu):** `./run.sh` — on `0.0.0.0:8000`; open TCP 8000 if firewalled.
- **Board/chat (Ubuntu):** `npm run dev` — leave `VITE_WS_URL` unset. On the tablet browse
  to `http://<ubuntu-ip>:5174` (board) / `:5173` (chat); each connects to
  `ws://<ubuntu-ip>:8000/ws` automatically.
- **Device (Tizen Hub):** the agent is in sync with ubuntu (re-synced through v6). Set
  `WS_URL=ws://<ubuntu-ip>:8000/ws` in `goalflow.conf`, deploy the `.tpk`, watch
  `dlogutil GOALFLOW`. (An Ubuntu device instead: `--connect ws://<ubuntu-ip>:8000/ws`.)
  - **No `--data` flag on Tizen** — a Tizen service takes no CLI args. It does the
    scratch-world thing *automatically*: the bundled `data/` in the `.tpk` is **read-only**,
    so on first run `DeviceConfig.ResolveDataDir()` seeds a **writable copy into the app Data
    dir** and mutates only that — the packaged seed is never touched, and nothing writes into
    the repo. To point it elsewhere (the `--data` equivalent) set `GOALFLOW_DATA_DIR=…` in
    `goalflow.conf`; for a clean world, delete that on-device dir, or send `control: reset`.

### Run — several homes on ONE cloud (multi-session)

The hub is **multi-session**: a session = one device agent + N UIs, keyed by a
**`device_id`**. Frames route only within a session, so two homes never see each other's
goals. Nothing to configure — each agent self-generates a persistent `device_id` and a
unique label. Two agents each need their OWN `--data` dir (the mock world is written to;
a fresh dir self-seeds from `./data`):

```bash
rm -rf data-a && dotnet run --project GoalFlow.Device.csproj -- --connect --data ./data-a --device-id hub-a --device-name "Kitchen Hub"
rm -rf data-b && dotnet run --project GoalFlow.Device.csproj -- --connect --data ./data-b --device-id hub-b --device-name "Cabin Hub"
```

Each UI auto-pairs with one agent; with several it shows a one-time picker (remembered per
browser). `?device=<id>` pins a tab for scripted runs.

---

## ⭐ THE SCRIPT — every prompt, in order

**Everything you type goes into the Bixby surrogate.** Watch the **chat UI** while a goal
is being created and the **board** for everything after.

Before you start: `GOALFLOW_PROFILE_PATH=./data/memory/demo_profile.json` in the cloud's
`.env` (keeps the run off the committed seed), and a fresh device world
(`rm -rf data-run1`).

| # | Say this into Bixby | What to expect | What you do |
|---|---|---|---|
| 1 | **Plan my weekly meal.** | Confirmation card: **three** constraint chips (peanut allergen · no pork · low sodium), each with its source underneath, and **two preferences** — *prefers white meat*, *workout-friendly*. No budget, no quiet hours. | **Confirm & plan** → watch it work → **Approve & Save** |
| 2 | *(nothing — press **Advance day** on the board)* | "What happened today" lists **two** things: Rohan's 12,400 steps, and 500 g of fish delivered. The meal card flags a review. | Open the card → **Adapt** → tomorrow becomes a high-protein fish dinner, and the *why* names **both** facts |
| 3 | **We'll be out ⟨day after tomorrow⟩ and ⟨the day after⟩ — get my home ready.** | Confirmation card: **no constraint chips**, three preferences — SmartThings away routine · energy saving · finish perishables. Plan: pause deliveries, away routine, arm security, **return readiness**. | Confirm & plan → **Approve & Save** |
| 4 | *(nothing — this is the moment)* | The chat holds **"Saving, and updating your other goals…"**. On the board the **meal card** gains one line: *"Plan changed — you're away Thu & Fri. Review."* | Open the meal goal: those two days now read **"Away — no meal planned"** |
| 5 | *(press **Advance day** twice)* | Quiet days — nobody is home. The home-away goal reaches 100% and moves to completed. | Just narrate it |
| 6 | **Find me a new apartment closer to my office.** | The chat opens, says this is not something this home can do, and **closes itself** after ~4s. Nothing is created on the board. | Nothing — that IS the beat |

> **Say the real weekday names in step 3.** The away window is whatever you say it is, so
> "the day after tomorrow and the day after that" is what keeps the demo correct on any day
> of the week. Presenting on a Tuesday? Say "Thursday and Friday".

> **What is guaranteed and what is not.** The chips, the preferences, the two-event day, the
> cross-goal rewrite and the refusal are **code** — deterministic, and gated. What the model
> chooses to COOK, and how it words a rejection, is not. Never promise a specific dinner
> from the stage.

---

## Act 1 — Create the meal goal (chat surface)

1. **Speak it.** *"Plan my weekly meal."* The chat surface opens on its own.
2. **The confirmation gate.** Three constraints, each with **where it came from** written
   underneath — *Account · always enforced*. Then two **preferences**, outlined rather than
   filled, because a preference shapes a plan and can never block one.
   - *Say:* "Before it plans, it shows me what it heard — and where each rule came from. I
     sign off on the understanding, not the plan."
3. **Watch it work** (~30–90s). The harness pipeline lights up engine by engine, each
   reporting a real number — *23 items · 4 expiring*, *12 considered, 1 rejected*, *3 rules
   held*. Open **Show details** for the labelled steps, including during planning.
   - *Say:* "Every number there is something it measured. The pipeline reports work; it
     isn't an animation."
4. **The plan.** Each day carries its **why** in cause-and-effect terms, and underneath it,
   what the planner **considered and rejected** — with the constraint that ruled each out.
   - *Say:* "A lookup table cannot reject. That line is the clearest evidence you'll get
     that something reasoned about this week."
5. **Approve & Save** → *"Saving your meal plan…"* → the chat closes itself.

---

## Act 2 — A day passes (board)

1. **Advance day.** Two things happened overnight and only one needs you: a hard training
   day (informational) and a fish delivery (material).
   - *Say:* "Telling me something happened and asking me to approve a change are different
     acts. It does both, and it knows which is which."
2. **Adapt.** The card flags a review; the goal detail proposes a swap whose reason names
   **both** facts. Approve, and the day morphs in place with an **Updated** badge.

---

## Act 3 — The home-away goal, and the moment it changes the other one

1. **Speak it.** *"We'll be out ⟨two weekdays⟩ — get my home ready."*
2. **No constraint chips**, three preferences. The food rules still ride on the dispatch and
   are still enforced — they simply cannot bite on any step of a home-prep plan.
   - *Say:* "Same household, same store of rules. A trip is constrained like a trip."
3. **The plan** pauses non-essential deliveries — never the repeat prescription, which the
   function refuses outright — hands the house to the SmartThings away routine, arms
   security, and ends with **return readiness**: resume the deliveries, run the robot
   vacuum, and plan the first meal back against a fridge that was deliberately emptied.
   - *Say:* "A checklist that ends at the front door has planned a departure, not a trip."
4. **Approve & Save.** The chat holds **"Saving, and updating your other goals…"** for as
   long as the work takes — the cloud does it *before* it closes the webview.
5. **The board.** The meal card now says *"Plan changed — you're away Thu & Fri. Review."*
   Open it: those two days read **"Away — no meal planned · from Get my home ready"**, and
   the detail page carries an **Already applied** notice with a *Got it* — not an approval.
   - *Say:* "I approved being away when I saved the second goal. Asking again — 'you said
     you're away Thursday, shall I stop planning Thursday's dinner?' — would be asking the
     same question twice. So it changed the plan, and it told me."
6. **Advance day twice.** Quiet days; nobody is home. The home-away goal completes.

---

## The closer — what it will not do

**"Find me a new apartment closer to my office."**

The chat opens, says this is outside what the home can act on, names what it *can* do, and
closes itself after about four seconds. There is no dismiss button: a refusal needs no
action from anyone.

> *Say:* "It knows its edges. That's the same judgement that stops it inventing a plan it
> can't deliver."

**Backup prompts**, in confidence order: *"Help me file my income tax return this year."* ·
*"Book my flights and hotels for Kerala next week and plan the sightseeing."* The refusal is
an LLM judgement against the device's advertised capabilities, so rehearse whichever you
plan to use.

---

## The technical view (optional, for engineers)

Toggle **"Show agent flow"** in the chat UI to reveal the live **WS message feed**:
`hello`, `user_goal`, streamed `agent_event`s (incl. `task_update`), `present_plan`,
`approval`, `status`, `suggestions`, the board's `board_snapshot`/`board_update`, and the
world tick `day_advanced`. Pair with [DESIGN.md](DESIGN.md) — §4 for the five harness
components, §6 for the frames.

**One-liners for Q&A:**
- *Why did the controls move to the board?* v3.1: the chat is the **creation** surface
  (understanding gate + initial approval); the board is the **life** surface (plan detail,
  monitoring, world events, and adaptation approvals). v3.2 went further: the world
  simulation is now ONE global **Advance day** on the main board — the sim clock is
  device-wide, so one tick fans out to every goal (a goal-less `control`), the device
  summarises the day as a `day_advanced` frame, and every card advances.
- *How does progress move?* The board's card numbers are cloud-derived. During planning it's
  the device's task DAG; once a goal is RUNNING, v3.2 makes progress **day-based** — where the
  sim date sits in the goal's time window — so **Advance day moves every card**. (A deliberate
  change from the older "progress only from the task DAG, never the clock" rule.)
- *Where do adaptation approvals happen?* A day-advance that materially changes a goal flags
  its card **"Approval needed"**; you tap it and approve on the **detail page** (the same
  AdaptationCard). The human still approves every change — the main page just points you to it.
- *Does the board talk to the device directly?* No — it's a web UI on the cloud hub, and the
  board is the device's face *logically*, through the hub. Every card and every raw frame it
  shows is device-originated and relayed; it just gained the device-facing writes (`control`,
  `approval`). A physical device↔board link is a production item, deferred (the device is a
  lean, outbound-only client; the board's transport endpoint is the only thing that would
  change).
- *The harness?* **Five generic components** — Capability Manager, Safety Policy Engine,
  Pre-check Engine, Task Manager, Product API Adapter — plus grounding/planner/approval/
  clock/trace. Zero product types; the fridge is a pack behind `IProductApiAdapter`.
- *Three gates?* Safety ("never" — a deterministic SK filter vs hard constraints),
  Approval ("waiting on a person" — tiered), Pre-check ("not yet" — is the world ready).
- *The board's numbers?* Derived from what the device actually SAID — the real **task DAG**
  (`task_update`) during planning, and once running, day-based against the goal's own window
  (v3.2; the window spans the goal's deadline so one Advance day can't falsely finish a
  goal — v3.6.1). Never invented. v2 had no task model; any progress bar then would have been
  fiction. `alerts` track what's **outstanding** and clear when an adaptation is resolved —
  approved *or* declined (v3.6.1/6.2).
- *Two tiers?* Cloud (LangGraph) owns talk/memory + interrupt-based HITL; device (SK) owns
  local truth + is the only thing that calls tools.

---

## Headless verification (no browser — a smoke test before the demo)

Each repo's gates run offline (no API key needed) and chain — run the latest:

```bash
# device (Ubuntu): the full chain M0–M8 + v6-M2/M3, gates 1–21
cd goal-flow-device-agent-ubuntu && ./verify/v6-m3/check.sh
# cloud: board fold, contract mirrors, per-goal constraint resolution (15), chat capture
# (16), persistence — plus the generic gate, which needs a key and is the slow one
cd goal-flow-cloud-agent && for g in verify_board verify_mirrors verify_constraints verify_capture verify_persistence verify_generic_gate; do .venv/bin/python scripts/$g.py; done
# a real end-to-end plan (needs a key):
cd goal-flow-device-agent-ubuntu && dotnet run --project GoalFlow.Device.csproj -- --contract data/sample-contract.json
```

> Always pass `--project GoalFlow.Device.csproj`. A bare `dotnet run --no-build` from the
> repo root can execute a **stale** binary.

---

## Troubleshooting (the ones that actually bite)

| Symptom | Fix |
|---|---|
| `HTTP 429 … rate-limited` from the LLM | You're on a `:free` model. Use `openai/gpt-oss-120b` in **both** `.env`. |
| `Resource temporarily unavailable (openrouter.ai:443)` mid-plan | A network/socket blip (a flaky link, a power cut). The device retries the grounding pass 3×; if it exhausts them the dispatch fails — reload the chat and resubmit once the link is stable. |
| A goal sits on "Working out the steps…" for a long time | A stalled provider stream. v3 has a per-call deadline (M6) — it retries; if it persists, the provider is down, check the cloud terminal. |
| Plan never appears | The reasoning model takes ~30–60s — narrate it. If the cloud terminal shows 429, fix the model. |
| Device disconnects mid-plan | Keep the **cloud stable** during a run (don't restart it mid-session) — a cloud restart drops the device. |
| Board shows nothing / a card is stuck | Reload the board (it re-fetches a fresh `board_snapshot`); a detail page that opened empty re-fills via `goal_state_get`. A card that won't move usually means the device is offline — it goes **At Risk / "went offline"**. |
| **Advance day** does nothing / no "what happened" card | Nothing has changed for that sim day (a quiet day shows "nothing changed"), or no goals are running yet — create + approve a goal first. Check the cloud terminal shows the `day_advanced` frame going out. |
| `[Errno 98] address already in use` (cloud) | A previous cloud holds :8000 → stop it (`ps -eo pid,args | grep uvicorn`, then `kill`). |
| A UI came up on the wrong port (5175/5176) | A stale Vite holds the default port. Stop the old dev servers and restart. Ports are assigned in START ORDER from 5173 — read each terminal's printed URL rather than assuming. |
| **v6:** the capture card never appears | Detection is an LLM call. Say a bare statement with no request in it ("we've gone vegan"), not "plan vegan dinners" — the second one is a goal, and it is treated as one. The cloud log shows `node=detect_constraints proposed=N statement_only=…`. |
| **v6:** `data/memory/family_profile.json` changed after a demo | An accepted capture wrote there. Set `GOALFLOW_PROFILE_PATH` to a scratch copy to stop it happening, and restore with `git checkout -- data/memory/family_profile.json`. (The write also reflows the file's formatting, so the diff looks bigger than the one entry added.) |
| **v6:** the device goes offline after a cloud restart | Restart the device agent too. Its reconnect backoff can outlast your patience; the board shows the goal **At Risk** in the meantime. |
| **v6:** a vacation goal still shows a $120 cap | You are running an old cloud. The resolution lives in `memory/store.py`; confirm with `.venv/bin/python scripts/verify_constraints.py` (gate 15). |
| Demo data got dirty (approvals/advancing wrote to it) | Restart the stack for a clean world, or restore only the runtime-mutated files (`git checkout -- data/appliances.json data/shopping_list.json data/inventory.json data/security.json data/notifications.json`) — do **not** `git checkout -- data/` wholesale (`daily_events.json`, thresholds, and the domain seeds are structure, not residue). (v3.2 dropped the per-goal Reset; a global reset is deferred.) |

Clean shutdown: stop the service processes (uvicorn, GoalFlow.Device, the three Vite servers). Check with `ps -eo pid,args | grep -E 'uvicorn|GoalFlow.Device|bin/vite'`.
