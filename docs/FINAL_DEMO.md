# GoalFlow — Final Demo Run-Sheet (v2)

The clean, end-to-end demo script for the **general goal-based agent** — two use cases (meal planning
and guest-dinner prep) on the same backbone, with live "watch it think" streaming, human-in-the-loop
approvals, and a proactive adaptation. This supersedes the milestone-wise runbook.

> **Thesis (say it once up front):** *one general agent + pluggable Family-Hub modules.* The LLM
> **plans** (Semantic Kernel function-calling over device plugins); **code checks** (a deterministic
> safety filter); the human approves; the agent keeps adapting as the world changes.

---

## 0. One-time setup

Three services on one machine (`~/ashu/git/`). Put your OpenRouter key in the two `.env` files and use
a **paid** model (free `:free` models are rate-limited — see Troubleshooting):

```bash
# goal-flow-cloud-agent/.env  and  goal-flow-device-agent-ubuntu/.env:
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-oss-120b     # a real tool-calling model
```

First-time-only install (once per repo):

```bash
cd goal-flow-cloud-agent      && python -m venv .venv && source .venv/bin/activate && pip install -e . && cp .env.example .env  # set OPENROUTER_API_KEY
cd goal-flow-device-agent-ubuntu && cp .env.example .env   # set OPENROUTER_API_KEY
cd goal-flow-agent-chat-ui    && npm install               # UI needs no .env — it derives the hub URL from its own host
```

### Run — all on one machine (the standard demo)

Three terminals. **These are the canonical commands — use them, not any older variant.**

```bash
# 1) cloud hub — run.sh binds 0.0.0.0:8000 and loads .env
cd goal-flow-cloud-agent && source .venv/bin/activate && ./run.sh
# 2) device agent — dials the cloud; bare --connect defaults to ws://localhost:8000/ws
cd goal-flow-device-agent-ubuntu && dotnet run --project GoalFlow.Device.csproj -- --connect
# 3) UI — Vite binds all interfaces (server.host)
cd goal-flow-agent-chat-ui && npm run dev
```

Open **http://localhost:5173** (kiosk/full-screen). The header shows **● open** when connected. Leave
"Show agent flow" **off** for the story; toggle it **on** for a technical audience.

Dates are **relative to the real today** — the sim clock and plan dates just work, no reset needed.

### Run — across machines (cloud on Ubuntu, UI on a tablet, device on the Tizen Hub)

Same commands, only the endpoints change (the UI derives the hub from whatever host served it):

- **Cloud (Ubuntu):** `./run.sh` — already on `0.0.0.0:8000`; open TCP 8000 if firewalled.
- **UI (Ubuntu):** `npm run dev` — **leave `VITE_WS_URL` unset**. On the **tablet**, browse to
  `http://<ubuntu-ip>:5173`; the UI connects to `ws://<ubuntu-ip>:8000/ws` automatically.
- **Device (Tizen Hub):** set `WS_URL=ws://<ubuntu-ip>:8000/ws` in `goalflow.conf`, deploy the `.tpk`,
  and watch `dlogutil GOALFLOW`. (An Ubuntu device instead: append the URL —
  `dotnet run --project GoalFlow.Device.csproj -- --connect ws://<ubuntu-ip>:8000/ws`.)

---

## Act 1 — Meal planning (the flagship)

1. **The goal.** Type: *"help my family eat healthier this week and reduce food waste"* → **Go**.
2. **Watch it think, round one** (~10–20s). The **progress rail** advances Interpreting →
   Grounding; a **thinking line** streams while the cloud interprets the goal and loads the
   family's memory.
3. **Confirm understanding (the first HITL gate).** Before anything reaches the device, an
   **Understanding card** appears: the objective restated in plain English, the household's hard
   constraints as chips (no-pork, the low-sodium medical need, budget, quiet hours…), and a
   one-line **thought** — the agent's approach. The rail pulses **Confirm**. Click **Confirm & plan**.
   - *Say:* "Before it plans anything, it tells me what it heard — I sign off on the
     *understanding*, not just the output."
4. **Watch it think, round two** (~30–60s — narrate this; it's the wow). The **cloud→device
   handoff** comet travels from the Cloud Agent to the Device Agent; the rail advances Planning →
   Checking; **tool-call chips** pop in and check off as the LLM calls the device's plugins:
   `Inventory · ListItems ✓`, `Inventory · GetExpiringItems ✓`, `Calendar · GetBusyEvenings ✓`,
   `Recipes · FindRecipes ✓`. **Skeleton** rows shimmer where the plan will land.
   - *Say:* "The fridge agent is calling its own tools — inventory, calendar, recipes — the model
     plans; nothing's hardcoded."
5. **The plan reveals as the hero.** The **"Knew:"** line re-confirms what it understood; a green
   **Safety ✓ passed** chip; the week's dinners with a why, tags; an **impact badge** ("uses N
   expiring items"). Below the plan, a strip of **World events** chips appears — the week's
   real-world curveballs, one per day, waiting to be fired.
   - *Say:* "The plan was checked by **code**, not the model — allergens, budget, quiet hours. LLM
     plans, code checks."
6. **Approve (HITL, tiered).** Two proposals: a light **"QUICK OK — add missing groceries"** and a
   firmer **"NEEDS YOUR APPROVAL — place grocery order"** (spends money). Click **Approve** → the
   device executes and it flips to **"Added ✓"**.
   - *Say:* "Nothing touched the shopping list until I approved. Reversible things are quiet; spending
     money needs a firm yes."
7. **It keeps thinking (adaptation, on demand).** Click a **World events** chip — e.g. *"Wed —
   Paneer spoiled"*. The chip shimmers to **firing**, the handoff comet travels again, and one
   scoped LLM call re-plans just that day: an **ADAPTATION** card appears — *"caught a change: the
   paneer spoiled and the rice ran out"* — with **Adapt / Decline**. Click **Adapt** → the affected
   day card **morphs in place** (old dish struck through, new dish slides in, the card pulses) and
   the chip settles to **fired ✓**. Fire another chip (e.g. the football-practice clash) to show it
   again.
   - *Say:* "There's no clock to babysit — I'm firing real-world events one at a time, and it
     re-plans just the day that's affected, live, on its own."

---

## Act 2 — Guest dinner (same agent, new goal → generality)

Show it's **not a meal app** — the identical backbone handles a different goal.

1. **The goal.** Type: *"we've got 6 people over Saturday for dinner — sort it out"* → **Go**.
2. **Watch it think.** Same rail, but now the chips are different tools: `Guests · GetEvent ✓`,
   `Guests · GetGuests ✓`, `Guests · GetDietaryConstraints ✓`, `Appliance · ListAppliances ✓`,
   `Recipes · FindRecipes ✓`.
   - *Say:* "Same agent, same harnesses — it just picked the tools that fit this goal."
3. **The plan is a prep timeline.** Instead of a weekly menu, a **timed schedule**: prep dishes,
   **preheat oven**, serve, **run dishwasher** — honoring the guests' dietary constraints (a
   **nut-allergic** guest → no nut dishes). Proposals include **appliance actions** + shopping.
4. **Approve.** Tiered again (appliance prep = light; place order = firm).
5. **Adaptation.** Advance toward Saturday → a guest's **RSVP updates to add a nut allergy** → an
   **ADAPTATION** card proposes a **nut-free swap**. Click **Adapt**.
   - *Say:* "A guest changed their RSVP; it caught the allergy and adjusted the menu."

---

## The technical view (optional, for engineers)

Toggle **"Show agent flow"** to reveal the live **WS message feed**: `hello`, `user_goal`,
streamed `agent_event`s, `present_plan`, `approval`, `status` — the whole mechanism, live. Pair with
`SYSTEM_OVERVIEW.md` (architecture + the 11 harness modules) and each repo's `CODE_GUIDE.md`.

**One-liners for Q&A:**
- *Harnesses?* 11 domain-agnostic modules — capability modules are SK plugins the LLM calls; steering
  modules (safety filter, approval/HITL interrupt, grounding, monitor/adapt, trace) guide the output.
- *Two tiers?* Cloud (LangGraph) owns talk/memory + interrupt-based HITL; device (SK) owns local truth
  + is the only thing that calls tools. They never shortcut each other.
- *Safety?* A deterministic SK function-invocation filter blocks tool calls that violate hard
  constraints (allergens, budget cap, quiet hours) — separate from the LLM.

---

## Headless verification (no browser — for a smoke test before the demo)

```bash
cd goal-flow-device-agent-ubuntu
dotnet run --project GoalFlow.Device.csproj -- --contract data/sample-contract.json        # meal plan_ready
dotnet run --project GoalFlow.Device.csproj -- --contract data/sample-contract-guest.json  # guest prep timeline
dotnet run --project GoalFlow.Device.csproj -- --simulate-week      # meal: 4 quiet days + the football adaptation
dotnet run --project GoalFlow.Device.csproj -- --simulate-guest     # guest: the nut-allergy RSVP adaptation
```

> Always pass `--project GoalFlow.Device.csproj`. A bare `dotnet run --no-build` from the repo root can
> execute a **stale** binary (the root csproj and the sln use different output paths).

---

## Troubleshooting (the ones that actually bite)

| Symptom | Fix |
|---|---|
| `HTTP 429 … rate-limited` from the LLM | You're on a `:free` model. Use `openai/gpt-oss-120b` (no `:free`) in **both** `.env`. |
| Plan never appears in the browser | The reasoning model takes ~30–60s — narrate the streaming. Check the cloud terminal; if 429, fix the model. |
| Device disconnects mid-plan / crashes | Keep the **cloud stable** during a run (don't restart it mid-session). The device answers WS pings on a background loop; a cloud restart mid-plan can still drop it. |
| `[Errno 98] address already in use` (cloud) | A previous cloud holds :8000 → `pkill -f "uvicorn goalflow"`. |
| UI dev server on :5174 | Stale Vite on :5173 → `pkill -f vite`, restart. |
| Demo data got dirty (approvals wrote to it) | UI **Reset week**. To reset files, only restore the runtime-mutated ones (`git checkout -- data/appliances.json data/shopping_list.json data/inventory.json data/shopping_list.json`) — do **not** `git checkout -- data/` wholesale (`daily_events.json` is a structural seed, not runtime residue). Sims use temp copies. |

Clean shutdown: `pkill -f "uvicorn goalflow"; pkill -f GoalFlow.Device; pkill -f vite`.
