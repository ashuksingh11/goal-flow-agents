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

## Out of scope (flagged)

Progress window is `start + span` (span = 7), so a 7-day plan hits 100% on day 8, not day 7 —
a separate minor off-by-one, not touched here.

## Verify

- Device gate chain m0–m8 + build; feed-alignment check.
- Live: create a meal goal → advance → the event edits **today's** dinner, and every surface
  shows "Tue, Jul 22" (browser via `agent-browser`).
