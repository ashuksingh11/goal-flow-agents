# GoalFlow — Final Demo Run-Sheet (v3)

The end-to-end demo script for the **general goal-based agent** on a Samsung Family Hub —
now with the **Agent Board** (a glanceable, multi-goal dashboard), **proactive
suggestions** (the agent proposes goals unprompted), **four use cases** on one backbone
(meal, guest dinner, vacation prep, birthday party), live "watch it think" streaming,
tiered human-in-the-loop approvals, honest negative paths, and proactive adaptation.

> **Thesis (say it once up front):** *one general agent + a pluggable Family-Hub product
> pack.* The LLM **plans** (Semantic Kernel over the device's plugins); **code checks** (a
> deterministic safety filter + a pre-check engine + a real task ledger); the human
> approves; the agent keeps adapting as the world changes. The harness is five generic
> components; the fridge is a swappable product pack behind one interface.

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
# 3) Agent Board — the hero surface (port 5174)
cd goal-flow-agent-board-ui && npm run dev
# 4) chat UI — the "watch it think" drill-in detail (port 5173)
cd goal-flow-agent-chat-ui && npm run dev
```

Open the **Agent Board at http://localhost:5174** (this is the home base). The chat UI at
**http://localhost:5173** is what a board card *drills into* — you rarely open it directly;
tapping a card opens it. Both headers show **● open** when connected.

Dates are **relative to the real today** — the sim clock and plan dates just work.

### Run — across machines (cloud on Ubuntu, board on a tablet, device on the Tizen Hub)

Same commands, only endpoints change (both UIs derive the hub from whatever host served
them):

- **Cloud (Ubuntu):** `./run.sh` — on `0.0.0.0:8000`; open TCP 8000 if firewalled.
- **Board/chat (Ubuntu):** `npm run dev` — leave `VITE_WS_URL` unset. On the tablet browse
  to `http://<ubuntu-ip>:5174`; it connects to `ws://<ubuntu-ip>:8000/ws` automatically. A
  card drills into the chat UI at `:5173` on the same host (set `VITE_CHAT_UI_URL` to
  override).
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

The board auto-pairs with one agent; with several it shows a one-time picker (remembered
per browser). `?device=<id>` pins a tab for scripted runs.

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

## Act 1 — A proactive suggestion becomes a goal (the M8 wow)

1. **Accept a suggestion.** Tap the **+** on **"Expiring Soon."**
   - *Say:* "I didn't type a goal — it noticed food about to spoil and offered. I'm just
     saying yes."
2. The suggestion turns into a **goal card** ("Weekly Meal Plan"), Waiting on the
   understanding gate. The suggestion leaves the list. **Nothing acted on its own** — a
   person accepting is what made it a goal.
3. **Drill in.** Tap the card → the **chat UI** opens on that goal: the **Understanding
   card** restates the objective, the household's hard constraints as chips (no-pork, the
   low-sodium medical need, budget **$120**, quiet hours **21:30–07:00**). Click **Confirm
   & plan.**
   - *Say:* "The board is the glance; this is the drill-in. Before it plans, it shows what
     it heard — I sign off on the *understanding*."
4. **Watch it think** (~30–60s). Tool-call chips check off as the LLM calls the device's
   plugins — `Inventory · GetExpiringItems ✓`, `Recipes · FindRecipes ✓`,
   `Budget · GetBudgetStatus ✓`. The plan reveals as the hero: the week's dinners that
   **use up the expiring items**, a green **Safety ✓ passed** chip, an **impact badge**.
   Meanwhile the **board card** fills in live — progress, next step, pending count.
   - *Say:* "The fridge agent calls its own tools; the model plans; nothing's hardcoded.
     And the plan was checked by **code** — allergens, the low-sodium need, the budget cap."
5. **Approve (tiered).** A light **"QUICK OK — add missing groceries"** and a firm
   **"NEEDS YOUR APPROVAL — place grocery order · $24.50"** (budget-capped, under $120).
   Approve → it flips to **Added ✓** and the board card advances.

---

## Act 2 — Vacation prep (the goal v2 refused)

Show the range: a goal the **v2 agent declined outright** as out-of-scope now runs — because
the device advertises what it can do, and the cloud judges against *that*.

1. **New goal.** On the board, **New Goal** → *"Get the house ready, we're away all next
   week."* → **Start.**
   - *Say:* "In v2 this was declined — 'not a meal-planning app.' Now the cloud asks the
     *device* what it can do, and the fridge can lock up, run the dishwasher, set reminders."
2. Confirm the understanding, watch it plan. The plan is a **home-prep checklist**:
   **Lock doors and arm the security system** (the new Security plugin — its arm step is
   pre-checked against the cameras being operational), **set the thermostat to eco**, **run
   the dishwasher before quiet hours**, **run the robot vacuum**, and a nice touch — **use
   up the food that would spoil while you're away**.
   - *Say:* "It did a dozen real things across security, appliances, and the fridge — one
     goal, the whole house."

---

## Act 3 — The board full of goals + the negative path

1. **Several goals at once.** Add **"Plan my son Aarav's birthday party next Sunday for 20
   kids"** (routes to the birthday domain; costs the cake + supplies against the $120 cap
   via the Budget plugin). Now the board shows **three cards** — Meal, Vacation, Birthday —
   each with its own progress, next step, ETA and alert count, and the summary bar tallies
   **On Track / At Risk / Waiting** at a glance.
   - *Say:* "This is why the board exists — several long-running goals, one screen, no
     hunting. The chat UI is single-goal; this is the whole home."
2. **The honest negative path.** In another terminal, simulate the world breaking —
   flip a flag the goal needs (e.g. `smartthings_connected` or `samsung_account` false in
   the agent's `data/device_state.json`), then start a goal that needs it. The card goes
   **Waiting** — not a false green — with the fix as its next step (*"you are signed out —
   sign in and this will resume"*). It **holds**, it doesn't pretend to finish.
   - *Say:* "When the world isn't ready, it says so honestly — Waiting, with what to do —
     and the goal waits rather than lying that it's done. That's a different gate from
     'not allowed' (safety) and 'needs you' (approval)."
3. **Adaptation, on demand.** Drill into the meal goal and fire a **World event** chip
   (e.g. *"Paneer spoiled"*) — one scoped LLM call re-plans just that day; the affected
   card **morphs in place**. Or, on a guest dinner, a late RSVP adds a nut allergy and it
   proposes a nut-free swap.
   - *Say:* "The plan is alive — it re-plans just the slice that changed, live."

---

## The technical view (optional, for engineers)

Toggle **"Show agent flow"** in the chat UI to reveal the live **WS message feed**:
`hello`, `user_goal`, streamed `agent_event`s (incl. `task_update`), `present_plan`,
`approval`, `status`, `suggestions`, the board's `board_snapshot`/`board_update`. Pair with
the device repo's `docs/HARNESSES.md` (the five components) and `V3_DESIGN_PROPOSAL.md`.

**One-liners for Q&A:**
- *The harness?* **Five generic components** — Capability Manager, Safety Policy Engine,
  Pre-check Engine, Task Manager, Product API Adapter — plus grounding/planner/approval/
  clock/trace. Zero product types; the fridge is a pack behind `IProductApiAdapter`.
- *Three gates?* Safety ("never" — a deterministic SK filter vs hard constraints),
  Approval ("waiting on a person" — tiered), Pre-check ("not yet" — is the world ready).
- *The board's numbers?* Derived from the device's real **task DAG** (`task_update`), never
  from the clock. v2 had no task model; any progress bar then would have been fiction.
- *Suggestions?* The device scans its own state (deterministic, not an LLM) and offers
  goals; accepting one submits it as an ordinary goal. Nothing acts unprompted.
- *Two tiers?* Cloud (LangGraph) owns talk/memory + interrupt-based HITL; device (SK) owns
  local truth + is the only thing that calls tools.

---

## Headless verification (no browser — a smoke test before the demo)

Each repo's gates run offline (no API key needed) and chain — run the latest:

```bash
# device (Ubuntu): the full chain M0–M8, gates 1–18
cd goal-flow-device-agent-ubuntu && ./verify/m8/check.sh
# cloud: the board fold, the contract mirrors, the generic gate, persistence
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
| A goal sits on "Working out the steps…" for a long time | A stalled provider stream. v3 has a per-call deadline (M6) — it retries; if it persists, the provider is down, check the cloud terminal. |
| Plan never appears | The reasoning model takes ~30–60s — narrate it. If the cloud terminal shows 429, fix the model. |
| Device disconnects mid-plan | Keep the **cloud stable** during a run (don't restart it mid-session) — a cloud restart drops the device. |
| Board shows nothing / a card is stuck | Reload the board (it re-fetches a fresh `board_snapshot`). A card that won't move usually means the device is offline — the card goes **At Risk / "went offline"**. |
| `[Errno 98] address already in use` (cloud) | A previous cloud holds :8000 → stop it (`ps -eo pid,args | grep uvicorn`, then `kill`). |
| Board on :5175, chat on :5174 | A stale Vite holds the default port. Stop the old dev servers and restart. |
| Demo data got dirty (approvals wrote to it) | Chat UI **Reset week**, or restore only the runtime-mutated files (`git checkout -- data/appliances.json data/shopping_list.json data/inventory.json data/security.json data/notifications.json`) — do **not** `git checkout -- data/` wholesale (`daily_events.json`, thresholds, and the domain seeds are structure, not residue). |

Clean shutdown: stop the four dev/service processes (uvicorn, GoalFlow.Device, the two Vite servers).
