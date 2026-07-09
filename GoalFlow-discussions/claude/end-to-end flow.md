**End-to-end flow — first pass (goal in → plan shown).** On startup, the device WS-connects to the cloud and registers; the UI opens its own WS to the cloud. Then:

1. **Goal in** (UI → cloud). User on the Hub: "help my family eat healthier next week, less waste." → `{type:"user_goal", text}`.
2. **Clarify** (cloud ↔ UI, cloud-only). LangGraph's ambiguity node asks back over the UI socket — "healthy = less processed, more veg? next week = which days?" — user answers. The device sees none of this; ambiguity is fully resolved before dispatch.
3. **Ground the family** (cloud). Memory node loads the tiny JSON: hard profile + soft preferences.
4. **Build + dispatch contract** (cloud → device). Decompose node emits the contract JSON, assigns `goal_id`, and sends the first wire crossing: `{type:"dispatch", <contract>}` down the device socket.
5. **Device pipeline** (device-internal — the harnesses light up, in order):
    - Task manager registers the task, status → `planning`.
    - Pre-check (stub) logs "access validated ✓".
    - Capability manager (stub) returns the known local APIs.
    - Product adapters pull mocked inventory + calendar.
    - Grounding folds both into one world-state object.
    - Planner (SK + LLM) turns world-state + contract → per-day dishes + missing items.
    - Safety gate (code) checks the dishes against `constraints.hard` → passed.
    - Approval broker wraps the missing items as a proposal, status → `awaiting_approval`.
    - Trace records each step — that log _is_ your demo activity feed.
6. **Plan up** (device → cloud). `{type:"plan_ready", payload:{plan, proposals, safety}}` up the device socket.
7. **Present** (cloud → UI). Relay node pushes `{type:"present_plan", …}` to the UI socket; the Hub shows the week's dinners, the "add bell peppers, lentils, yogurt?" prompt, and a small "safety: passed" indicator — that indicator is a cheap, high-impact management moment.