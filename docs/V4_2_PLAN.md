# V4.2 — day-advance targeting fix + real-date display

Branches: `v4.2` in `goal-flow-device-agent-ubuntu`, `goal-flow-agent-board-ui`,
`goal-flow-agent-chat-ui`, `goal-flow-agents` (created off `v4`). Cloud + Tizen untouched.

Two user-reported items:

1. **Day-advance off-by-one.** Advancing from day 1 → day 2 changed *Day 1*'s dinner
   (already passed); it should change the day you land on.
2. **Show real dates** ("Tue, Jul 22") instead of "Day 1 / Day 2 …".

## Issue 1 — root cause + fix

The meal-week world feed (`goal-flow-device-agent-ubuntu/data/daily_events.json`) carries
two numbers per event:

- `day_offset` → resolved at goal-creation into a **fire date** = `goalStart + day_offset`
  (`MockFamilyHubAdapter.ResolveOffset`).
- `day` → the plan **day it edits** (`MealPlanObserver.BuildChange` → `TargetDay`).

The seed had **`day_offset == day`** for every event, and the observer fires an event when
the clock *reaches or passes* its date. So `day1-restock` (offset 1) doesn't fire until the
clock hits day 2, yet it edits Day 1 — a dinner already in the past. Every event landed one
day after the dinner it changed.

**Fix (data + wording only): set `day = day_offset + 1` for each event.** The plan day an
event edits now equals the day the clock is on when it fires. Advance into day D → that day's
dinner changes. `steer` strings and the file `comment` header updated to match; the
`day_offset` (fire) vs `day` (target) = +1 invariant is documented in the seed so it can't
silently regress. No code change — the mechanism already read these fields correctly; it was
fed misaligned data. After the fix an event's resolved `date` equals its target day's date,
which Issue 2 reuses for event titles.

## Issue 2 — real dates instead of "Day N"

The sim clock already runs on real calendar dates and the plan-item contract already carries
`when?` (device `when: str|None` → cloud relay → board/chat `when?: string`) — it was simply
ignored by the renderers. So this is **rendering + one device string + populating `when`**;
**no contract / mirror / gate-14 change.** `day` stays in frames (progress + anchoring use
it); it just stops being displayed.

Format: **"Tue, Jul 22"** (weekday, short month, day).

- **Device:** stamp `When` on meal-plan items in `AssignPlanDays` = goal-start anchor
  `+ (Day-1)`, preserved across adaptations by carrying prior `When` by Day.
  `MealPlanObserver.BuildChange.Description` → `"{date} - {summary}"`. Sweep other observers
  for user-visible "Day N".
- **Board UI:** `PlanView`/`PlanCard` render `formatWhen(item.when)` (fallback derived date,
  last-resort "Day N"); `AdvanceDayCard` eyebrow "Today · Tue, Jul 22"; `GoalDetail` history
  shows the date. New `formatWhen` helper.
- **Chat UI:** `PlanCard` + `StatusTimeline` "Day N" → date.

## V4.2 fix — adapted dinner keeps its date (2026-07-22)

Advancing a day and adapting a dinner shifted that row's date. The adapt prompt asked the model
for a `"when"`, and `ApplyPatch` only kept the original date when the incoming one was empty — so
the model's emitted date overrode the correct one. An adaptation changes the DISH, not the date.
Fix (date is device-owned): `NormalizeAdaptationPatch` forces `When=target.When`; `ApplyPatch`
now ALWAYS restores an existing item's `When`; `"when"` dropped from the adapt prompt schema.
Verified headless (`--simulate-week`): five consecutive adaptations each kept the correct
sequential date (Day 2→07-23 … Day 6→07-27 = anchor + Day-1). Ported to Tizen; builds + gates pass.

## Out of scope (flagged)

Progress window is `start + span` (span = 7), so a 7-day plan hits 100% on day 8, not day 7 —
a separate minor off-by-one, not touched here.

## Verify

- Device gate chain m0–m8 + build; feed-alignment check.
- Live: create a meal goal → advance → the event edits **today's** dinner, and every surface
  shows "Tue, Jul 22" (browser via `agent-browser`).

## V4.2 follow-up — debuggability + "watch it think" (2026-07-22)

Two more user-reported fixes.

**Meaningful logs (fix #1).** Added compact `key=value` decision/timing logs matching the
existing style: device `grounding_done`/`compose_done` (+elapsed_ms, counts),
`world_change_material` (target_day), `world_tick`, `approval_received` (approved/declined);
cloud `ui_bound` (surface + device_online). `agent_event` Info lines are now compact
(`tool_call seq=3 Inventory.ListItems`) instead of full-JSON dumps.

**`agent_event thinking` — show it properly, not remove (fix #2).** The frames drive chat-ui's
live reasoning, but the UI previously showed mostly HARDCODED phase strings and only the latest
140 chars of the real stream — so the WS/log flood bought almost no UX. Two parts:
- *UI:* `AgentStream` now renders the FULL streamed reasoning as a scrolling, auto-scrolling
  transcript (accent rail + streaming caret); planning indicator + tool chips stay below.
- *Log hygiene:* the streamed per-chunk `thinking` drops to **Debug** on both device
  (`Trace.EmitAsync`) and cloud (`log_frame`, `_HIGH_FREQUENCY_TYPES`), so the Info stream is a
  clean lifecycle timeline; `--verbose` / `LOG_LEVEL=DEBUG` restores it. Verified live: 0
  thinking/agent_event lines at Info; transcript streams the real reasoning.

**Tizen:** ported all v4.2 device changes (date fix + logging) to `goal-flow-device-agent-tizen`
`v4.2` (files were byte-identical to ubuntu; wholesale copy); builds clean. `DeviceHost.cs`
`SetMinimumLevel(Information)` (LOG_LEVEL via goalflow.conf) suppresses Debug like ubuntu and
maps to dlog priorities (thinking→D, meaningful→I).

## V4.2 fix — configurable LLM call timeouts (2026-07-22)

Planning kept cancelling mid-compose with `transient provider error (TaskCanceledException)`.
Cause: the non-streaming compose call ran under a HARDCODED 90s total deadline (`Deadline` →
`CancelAfter`), so a large/slow model (deepseek-v4-pro, gpt-oss-120b) or provider load pushed a
legitimate compose past 90s → the CTS cancelled the socket read → retried, wasting 90s each time.
Fix: raise defaults (compose 90→180s, grounding stream 150→210s) and make both tunable via
`LLM_CALL_TIMEOUT_SECONDS` / `LLM_STREAM_TIMEOUT_SECONDS` — through `AgentSettings`, overridden
only when set to a positive int (floored at 10s). Env on ubuntu (`.env`), `goalflow.conf` on Tizen
(via `DeviceConfig`). Startup logs `llm_budgets model=… call_timeout_s=… stream_timeout_s=…`.
Ported to Tizen (`DeviceHost` threads settings into `CreateAgent`); both build; gates m0–m6 pass;
verified default 180/210 vs env override 60/90.
