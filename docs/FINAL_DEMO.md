# GoalFlow — Final Demo Run-Sheet (v3.1)

The end-to-end demo script for the **general goal-based agent** on a Samsung Family Hub.
v3.1 splits the surfaces by moment: the **chat UI is where you CREATE a goal** (speak it,
confirm what the agent understood, approve the plan), and the **Agent Board is where a
goal LIVES** — the full plan detail, monitoring, the world-event simulation, and any
world-event approvals. Once the initial plan is approved, the chat hands off and the board
takes over.

> **Thesis (say it once up front):** *one general agent + a pluggable Family-Hub product
> pack.* The LLM **plans** (Semantic Kernel over the device's plugins); **code checks** (a
> deterministic safety filter + a pre-check engine + a real task ledger); the human
> approves; the agent keeps adapting as the world changes. The harness is five generic
> components; the fridge is a swappable product pack behind one interface.

> **The two surfaces (say it once):** *Chat = create. Board = live.* You talk to the agent
> on the chat surface to start a goal and sign off on its plan; then the board drives the
> goal's whole life — you watch it, simulate the world, and steer it there. Both are just
> web UIs on the cloud hub; the board is the device's face, logically, via the hub.

---

## 0. One-time setup

**Four surfaces**, three of them services (`~/ashu/git/`). Put your OpenRouter key in the
two `.env` files and use a **paid** model (free `:free` models are rate-limited):

```bash
# goal-flow-cloud-agent/.env  and  goal-flow-device-agent-ubuntu/.env:
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-oss-120b     # a real tool-calling model
```

First-time-only install (once per repo): `.venv` + `pip install -e .` for the cloud;
`npm install` for each UI.

### Run — all on one machine (the standard demo)

Four terminals. **These are the canonical commands.**

```bash
# 1) cloud hub — binds 0.0.0.0:8000 and loads .env
cd goal-flow-cloud-agent && source .venv/bin/activate && ./run.sh
# 2) device agent — dials the cloud; bare --connect defaults to ws://localhost:8000/ws
cd goal-flow-device-agent-ubuntu && dotnet run --project GoalFlow.Device.csproj -- --connect
# 3) Agent Board — where a goal LIVES (port 5174)
cd goal-flow-agent-board-ui && npm run dev
# 4) chat UI — where you CREATE a goal (port 5173)
cd goal-flow-agent-chat-ui && npm run dev
```

Open **both**: the **chat UI at http://localhost:5173** (you start goals here) and the
**Agent Board at http://localhost:5174** (goals live here). On the real Hub the shell swaps
between them — chat full-screen while you create, then the board full-screen for the rest.
In the browser demo you keep both tabs and switch by hand at the hand-off. Both headers show
**● open** when connected.

Dates are **relative to the real today** — the sim clock and plan dates just work.

### Run — across machines (cloud on Ubuntu, board on a tablet, device on the Tizen Hub)

Same commands, only endpoints change (both UIs derive the hub from whatever host served
them):

- **Cloud (Ubuntu):** `./run.sh` — on `0.0.0.0:8000`; open TCP 8000 if firewalled.
- **Board/chat (Ubuntu):** `npm run dev` — leave `VITE_WS_URL` unset. On the tablet browse
  to `http://<ubuntu-ip>:5174` (board) / `:5173` (chat); each connects to
  `ws://<ubuntu-ip>:8000/ws` automatically.
- **Device (Tizen Hub):** the agent is re-synced to v3 (M9). Set `WS_URL=ws://<ubuntu-ip>:8000/ws`
  in `goalflow.conf`, deploy the `.tpk`, watch `dlogutil GOALFLOW`. (An Ubuntu device
  instead: `--connect ws://<ubuntu-ip>:8000/ws`.)

### Run — several homes on ONE cloud (multi-session)

The hub is **multi-session**: a session = one device agent + N UIs, keyed by a
**`device_id`**. Frames route only within a session, so two homes never see each other's
goals. Nothing to configure — each agent self-generates a persistent `device_id` and a
unique label. Two agents each need their OWN `--data` dir (the mock world is written to;
a fresh dir self-seeds from `./data`):

```bash
dotnet run --project GoalFlow.Device.csproj -- --connect --data ./data-a --device-id hub-a --device-name "Kitchen Hub"
dotnet run --project GoalFlow.Device.csproj -- --connect --data ./data-b --device-id hub-b --device-name "Cabin Hub"
```

Each UI auto-pairs with one agent; with several it shows a one-time picker (remembered per
browser). `?device=<id>` pins a tab for scripted runs.

---

## The board is home (open with this)

Open the Agent Board. Even with **no goals yet**, it's already working: an **Upcoming &
Suggested** section shows cards the agent raised on its own by scanning the fridge —
**"Expiring Soon · 2 items in 3 days · spinach, yogurt"** and **"Grocery Restock · 4 items
running low."**

> *Say:* "This is the home screen. Before I've asked for anything, it has already looked
> at the fridge and is offering to act. Everything on this board is one glance — what's
> running, how far along, what needs me."

---

## Act 1 — Create a goal on the chat surface (understanding → plan → approve)

1. **Start a goal.** On the real Hub you press the agent icon and *speak* it; in the demo,
   accept the board's **"Expiring Soon"** suggestion (tap **+**) or type on the **chat UI**:
   *"Plan meals that use up the food expiring this week."*
   - *Say:* "I talk to the agent to start a goal. On the Hub that's my voice; here it's the
     chat surface. It even offered this one itself — I'm just saying yes."
2. **The chat takes over — confirm the understanding.** The chat shows the **Understanding
   card**: the objective restated, and the household's hard constraints as chips (no-pork,
   the low-sodium medical need, budget **$120**, quiet hours **21:30–07:00**, peanut
   allergen). Click **Confirm & plan.**
   - *Say:* "Before it plans, it shows me what it *heard* — I sign off on the understanding,
     not the plan yet. That's the first gate."
3. **Watch it think** (~30–60s). Tool-call chips check off as the LLM calls the device's
   plugins — `Inventory · GetExpiringItems ✓`, `Recipes · FindRecipes ✓`,
   `FamilyProfiles · GetProfiles ✓`. The plan reveals as the hero: the week's dinners that
   **use up the expiring items**, a green **Safety ✓ passed** chip, an **impact badge**.
   Meanwhile the **board card** (other tab) fills in live — progress, next step, pending.
   - *Say:* "The fridge agent calls its own tools; the model plans; nothing's hardcoded. And
     the plan was checked by **code** — allergens, the low-sodium need, the budget cap."
4. **Approve (tiered).** Light **"QUICK OK — add missing groceries"** and a firm
   **"NEEDS YOUR APPROVAL — place grocery order"** (budget-capped, under $120). Approve them.
5. **The hand-off.** The chat shows a green banner: **"Plan approved — your Agent Board is
   now driving this goal."** That's the cue to switch to the board.
   - *Say:* "Creation is done. Everything from here — watching it, changing it as the week
     unfolds — happens on the board. The chat's job was to start it and get my sign-off."

---

## Act 2 — The board drives the goal's life (detail page + world events)

1. **Switch to the board and tap the card.** It opens the goal's **detail page** — the full
   7-day plan, the "Knew" constraints, Safety ✓, impact, a **live activity** line, and a
   **What has happened** history. (No jumping back to the chat — the board owns this now.)
   - *Say:* "This is where the goal lives for the next seven days. The whole plan, what it's
     done, what's coming — one surface."
2. **Simulate the world.** The detail page has a **World events** strip — the curated things
   that happen during the week: *Groceries arrive, Paneer spoiled, Football practice added,
   Grandma joins.* (They unlock only once the plan is approved.) Fire **"Football practice
   added Wed."**
   - *Say:* "The device is a service that watches the world. I'll fast-forward one real
     change — a calendar clash lands mid-week."
3. **Approve the adaptation — on the board.** The agent catches the change and proposes a
   fix, right here on the board: a **"Caught a change"** card — *"prep the wrap earlier so
   dinner's ready before the 18:00 practice."* Click **Adapt.**
   - *Say:* "It re-planned just the slice that changed. And because the board is the live
     surface now, it asks me *here* — not back on some chat window I've closed."
4. **The plan morphs in place.** The affected day updates with an **Updated** badge, an
   impact delta (*"25 min saved"*), and the history logs the swap. The fired event shows
   **✓**.
   - *Say:* "The plan is alive — it changes in place as the world changes, and I steer it
     from the one screen that's in front of me."

---

## Act 3 — The board full of goals + the range

1. **Several goals at once.** Start two more (chat surface, or board **New Goal**):
   - *"Get the house ready, we're away all next week."* — the goal **v2 refused** as
     out-of-scope. It runs now because the device advertises Security/Appliance/Reminders
     and the cloud judges against *that*: lock doors, arm security (pre-checked against the
     cameras), thermostat to eco, run the dishwasher before quiet hours, and use up the food
     that would spoil while away.
   - *"Plan my son Aarav's birthday party next Sunday for 20 kids."* — routes to the
     birthday domain; costs the cake + supplies against the $120 cap.
   Now the board shows **three cards** — Meal, Vacation, Birthday — each with its own
   progress, next step, ETA and alerts, and the summary bar tallies **On Track / At Risk /
   Waiting** at a glance.
   - *Say:* "This is why the board exists — several long-running goals, one screen. The chat
     started each one; the board runs them all."
2. **The honest negative path.** Simulate the world breaking — flip a flag a goal needs
   (e.g. `smartthings_connected` false in the agent's `data/device_state.json`) and start a
   goal that needs it. The card goes **Waiting** — not a false green — with the fix as its
   next step (*"you are signed out — sign in and this will resume"*). It **holds**; it
   doesn't pretend to finish.
   - *Say:* "When the world isn't ready, it says so honestly — Waiting, with what to do.
     That's a different gate from 'not allowed' (safety) and 'needs you' (approval)."

---

## The technical view (optional, for engineers)

Toggle **"Show agent flow"** in the chat UI to reveal the live **WS message feed**:
`hello`, `user_goal`, streamed `agent_event`s (incl. `task_update`), `present_plan`,
`approval`, `status`, `suggestions`, the board's `board_snapshot`/`board_update`. Pair with
the device repo's `docs/HARNESSES.md` (the five components) and `V3_DESIGN_PROPOSAL.md`.

**One-liners for Q&A:**
- *Why did the controls move to the board?* v3.1: the chat is the **creation** surface
  (understanding gate + initial approval); the board is the **life** surface (plan detail,
  monitoring, world events, and world-event adaptation approvals). The chat closes after
  approval, so the live surface is where the steering must be.
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
- *The board's numbers?* Derived from the device's real **task DAG** (`task_update`), never
  from the clock. v2 had no task model; any progress bar then would have been fiction.
- *Two tiers?* Cloud (LangGraph) owns talk/memory + interrupt-based HITL; device (SK) owns
  local truth + is the only thing that calls tools.

---

## Headless verification (no browser — a smoke test before the demo)

Each repo's gates run offline (no API key needed) and chain — run the latest:

```bash
# device (Ubuntu): the full chain M0–M8, gates 1–18
cd goal-flow-device-agent-ubuntu && ./verify/m8/check.sh
# cloud: the board fold, the contract mirrors (gate 14), the generic gate, persistence
cd goal-flow-cloud-agent && for g in verify_board verify_mirrors verify_generic_gate verify_persistence; do .venv/bin/python scripts/$g.py; done
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
| World-event chips are greyed out on the board | The strip unlocks only once the goal's initial plan is approved (on the chat). Approve first. |
| `[Errno 98] address already in use` (cloud) | A previous cloud holds :8000 → stop it (`ps -eo pid,args | grep uvicorn`, then `kill`). |
| A UI came up on the wrong port (5175/5176) | A stale Vite holds the default port. Stop the old dev servers and restart. |
| Demo data got dirty (approvals wrote to it) | Board **Reset week** on the goal's detail page, or restore only the runtime-mutated files (`git checkout -- data/appliances.json data/shopping_list.json data/inventory.json data/security.json data/notifications.json`) — do **not** `git checkout -- data/` wholesale (`daily_events.json`, thresholds, and the domain seeds are structure, not residue). |

Clean shutdown: stop the four dev/service processes (uvicorn, GoalFlow.Device, the two Vite servers).
