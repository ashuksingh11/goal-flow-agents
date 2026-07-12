# GoalFlow — Demo Runbook

> **HISTORICAL — v1. Superseded by [FINAL_DEMO.md](FINAL_DEMO.md) and [V2_DESIGN_PROPOSAL.md](V2_DESIGN_PROPOSAL.md). Kept for reference only.**

How to deploy the three services, run the demo end-to-end, and troubleshoot. Read
[`SYSTEM_OVERVIEW.md`](SYSTEM_OVERVIEW.md) first for the architecture.

> **TL;DR** — three terminals: (1) cloud `uvicorn` on :8000, (2) device `dotnet run -- --connect`,
> (3) UI `npm run dev` on :5173. Open the UI, type the goal, approve the plan, then use the "Demo
> controls" to advance through the week until Wednesday's adaptation fires.

---

## 0. Prerequisites

| Need | Version | Check |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| .NET SDK | 8.x | `dotnet --version` |
| Node.js | 18+ | `node --version` |
| An OpenRouter API key | — | https://openrouter.ai/keys (needed for M2+ LLM paths) |
| A Chromium browser | — | for the UI |

All three repos are siblings (e.g. under `~/ashu/git/`). Paths below assume that.

### API key + model (one-time)

The cloud and device read `OPENROUTER_*` from a local `.env` (gitignored). Put your key in **both**:

```bash
cd goal-flow-cloud-agent        && cp -n .env.example .env
cd ../goal-flow-device-agent-ubuntu && cp -n .env.example .env
# then edit both .env files: set OPENROUTER_API_KEY=sk-or-...
```

**Model choice matters.** Use a **paid** model id — free (`:free`) models on OpenRouter are
account-throttled and return HTTP 429 (see Troubleshooting). We use:

```
OPENROUTER_MODEL=openai/gpt-oss-120b
```

`gpt-oss-120b` is a **reasoning model** (it spends tokens thinking before answering), so the code
budgets generous `max_tokens` and reads the final `content`. A full demo run costs ≈ a fraction of
a cent. Quick sanity check that your key + model work:

```bash
KEY=$(grep OPENROUTER_API_KEY goal-flow-cloud-agent/.env | cut -d= -f2-)
curl -s https://openrouter.ai/api/v1/chat/completions -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-oss-120b","max_tokens":300,"messages":[{"role":"user","content":"Reply with one word: PONG"}]}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('choices',[{}])[0].get('message',{}).get('content') or d.get('error'))"
# expect: PONG
```

---

## 1. Deploy — cloud agent (the hub)

```bash
cd goal-flow-cloud-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                     # first time only
uvicorn goalflow_cloud.server:app --host 127.0.0.1 --port 8000
```

Healthy when you see `Application startup complete` and `Uvicorn running on http://127.0.0.1:8000`.
It serves the WebSocket hub at `ws://localhost:8000/ws`. Leave it running.

## 2. Deploy — device agent

The device opens an **outbound** WS to the cloud, so start it *after* the cloud is up.

```bash
cd goal-flow-device-agent-ubuntu
dotnet build                         # first time (or after code changes)
WS_URL=ws://localhost:8000/ws dotnet run --no-build -- --connect
```

Healthy when the log shows `connecting to ws://localhost:8000/ws`, `sent hello frame`,
`received hello_ack`. Logs go to **stderr**; leave it running. Default planner is `rules`
(deterministic, demo-safe). To use the LLM planner instead: add `--planner llm`.
> *(Retired v1 design: the `--planner` flag and the rules/scripted planner no longer exist —
> v2 planning is LLM-only. See the device repo's `README.md`/`CODE_GUIDE.md`.)*

## 3. Deploy — chat UI

```bash
cd goal-flow-agent-chat-ui
cp -n .env.example .env               # VITE_WS_URL=ws://localhost:8000/ws
npm install                           # first time only
npm run dev -- --host 127.0.0.1 --port 5173
```

Open **http://127.0.0.1:5173**. The header shows a green **● Open** indicator when the WS is
connected.

---

## 4. Run the demo (browser walkthrough)

This is the marquee flow — story on the left, mechanism on demand on the right.

1. **Cold open.** The UI is connected (green ● Open). Optionally tick **"Show agent flow"** (top
   right) to reveal the live WS message feed for a technical audience.
2. **The goal.** Type: *"help my family eat healthier this week and reduce food waste"* → **Send**.
   - The cloud runs its LangGraph graph + LLM to build the contract (**~10–25s** — it's a reasoning
     model; a plan card appears when done).
3. **The plan reveals.** A "WEEKLY PLAN" card with:
   - a **"Knew:" line** (what the system understood — no pork, mushroom dislike, Aarav's football),
   - a **Safety: passed ✓** chip,
   - 5 dinners with why-tags (note Wednesday's `calendar_aarav_football_practice_18:00`),
   - a shopping-list **proposal** with **Approve / Decline**,
   - **impact badges** (0 pork meals · 5 veg-forward dinners · items used before expiry · grocery items).
4. **Approve (the "commit" rung).** Click **Approve** → the device executes and the UI shows
   **"5 items added to shopping list"**. (In the device log: `EffectExecutor executed …`.)
5. **Advance the week.** Use the **DEMO CONTROLS** strip: click **Advance day ▶**.
   - **Mon, Tue** → calm "on track" statuses ("reconciled inventory; reminder set for …").
   - **Wed** → the agent catches the conflict: an **"ADAPTATION — Schedule change caught"** card
     appears with a *"Judgment needed"* badge, the trigger *"Aarav football Wed 18:00 — prep window
     shrinks"*, and an **Adapt / Decline** action.
6. **Adapt (the "adapt" rung).** Click **Adapt** → the device creates a prep reminder and the card
   shows **"prep reminder created"**.
7. **Reset.** Click **Reset week** to run it again from Monday.

**The wow is the judgment, not repetition:** four quiet days and one smart Wednesday adaptation.

### Headless verification (no browser)

- **Device planner + safety, standalone:**
  ```bash
  cd goal-flow-device-agent-ubuntu
  dotnet run -- --contract data/sample-contract.json --planner rules   # prints plan_ready JSON
  dotnet run -- --contract data/sample-contract.json --planner llm     # real OpenRouter call (or falls back)
  ```
  *(Retired v1 design: `--planner rules`/`--planner llm` no longer exist — v2 planning is
  LLM-only, always via `--contract data/sample-contract.json` with no `--planner` flag.)*
- **The whole adaptation week, headless:**
  ```bash
  dotnet run -- --simulate-week          # Mon..Fri sustain ticks; Wed = material + adaptation proposal; auto-resets
  ```
- **Cloud graph produces a real contract:**
  ```bash
  cd goal-flow-cloud-agent && source .venv/bin/activate
  python scripts/run_graph_demo.py       # prints the LLM-built Task Contract
  ```

---

## 5. Demo run-sheet (suggested narration)

| Beat | Screen | Say |
|---|---|---|
| 1 | UI connected | "One tablet talks to a cloud agent, which delegates to an agent on the fridge." |
| 2 | Type goal | "A fuzzy, human goal — no forms." |
| 3 | Plan reveals | "It already knew the family: no pork, mushrooms out, and that Wednesday is football night." |
| 4 | Safety chip | "The plan was checked by *code* on the device, not the model — LLM plans, code checks." |
| 5 | Approve | "Nothing happened to the shopping list until I approved." |
| 6 | Advance to Tue | "Quiet days just confirm and set reminders." |
| 7 | Advance to Wed | "Here it earns its keep — it caught the football clash and proposed a fix on its own." |
| 8 | Adapt | "One tap, and it adjusted." |
| 9 | Show agent flow | (for engineers) "Every message and gate is right here." |

---

## 6. Troubleshooting

### LLM / OpenRouter

| Symptom | Cause | Fix |
|---|---|---|
| `HTTP 429 … temporarily rate-limited upstream` | You're on a `:free` model. Free variants are account-throttled to ~1 req/15–20s and often fully blocked. | Drop the `:free` suffix — use `openai/gpt-oss-120b`. Set it in **both** `.env` files. |
| `HTTP 401` | Bad/empty API key. | Check `OPENROUTER_API_KEY` in the `.env` (no quotes/spaces after `=`). |
| LLM call returns empty `content` | `gpt-oss-120b` is a reasoning model; a small `max_tokens` is all consumed by hidden reasoning. | Already handled in code (generous tokens). If you added a custom call, raise `max_tokens` to ≥ 300. |
| Plan card never appears (browser) | The cloud LLM call is just slow (reasoning model, 10–25s), or it 429'd. | Wait ~25s. Check the cloud terminal for a fallback/error log; if 429, fix the model per above. The cloud falls back to a scripted contract on failure, so a plan should still appear. *(Retired v1 design: v2 is LLM-only end to end and fails loudly instead of falling back to a scripted contract.)* |

### WebSocket / connectivity

| Symptom | Cause | Fix |
|---|---|---|
| UI shows red/"closed" indicator | Cloud not running, or wrong `VITE_WS_URL`. | Start the cloud first; confirm `.env` has `VITE_WS_URL=ws://localhost:8000/ws`; restart `npm run dev` after editing `.env`. |
| Device log: `connecting…` then retries forever | Cloud not up yet, or wrong `WS_URL`. | Start the cloud first. The device auto-reconnects; it will attach once the cloud is up. |
| `[Errno 98] address already in use` (cloud) | A previous cloud is still bound to :8000. | Find and kill it: `ss -ltnp \| grep :8000` then `kill -9 <pid>` (or `pkill -f "uvicorn goalflow"`). |
| UI dev server starts on :5174 instead of :5173 | A stale Vite is holding :5173. | `pkill -f vite`, then restart. |
| Nothing happens on "Advance day" | Device not connected, or no active plan yet. | Send a goal first (controls only act on an active plan); confirm the device shows `received hello_ack`. |

### Build / environment

| Symptom | Cause | Fix |
|---|---|---|
| `NU1605` package downgrade error (.NET) | Semantic Kernel pulls `System.Text.Json`/DI 10.x; pinning 8.x conflicts. | The `.csproj` floats those (`Version="*"`). Don't pin them to 8.x. |
| `ModuleNotFoundError` / uvicorn can't find app (cloud) | venv not activated or deps not installed. | `source .venv/bin/activate && pip install -e .` |
| UI type errors on `npm run build` | Stale `node_modules` or TS mismatch with `contract.ts`. | `rm -rf node_modules && npm install`; ensure `contract.ts` matches `CONTRACT.md`. |

### Demo data residue

The device writes to real `data/*.json` when you approve/adapt during a live run (shopping list,
reminders). To reset between demos:

- In the UI: click **Reset week** (restores the device's in-memory world + clock).
- On disk (device repo): `git checkout -- data/` restores the seed JSON files.
- `--simulate-week` uses a temp copy and never dirties `data/`.

### Clean shutdown

```bash
pkill -f "uvicorn goalflow"   # cloud
pkill -f "GoalFlow.Device"    # device
pkill -f vite                 # UI
```

---

## 7. Deploying on one Ubuntu box (demo machine)

For the actual demo, all three run on the same Ubuntu host on `localhost`. Recommended order:
**cloud → device → UI**, each in its own terminal (or `tmux` pane). Point a browser (kiosk/full
screen) at `http://localhost:5173`. If you want the device on a separate machine (or the real Hub
later), set `WS_URL` on the device to the cloud host's IP (`ws://<cloud-ip>:8000/ws`) and start the
cloud with `--host 0.0.0.0`.
