# V5.1 — The Working Column ("one column for the run")

## Why

v5 made the harness visible. It also made the chat surface **crowded**: the harness pipeline
was a 7-row panel, the reasoning transcript sat beside it, the plan grew underneath, and a
phase rail ran above all of it. On the Family Hub's portrait screen that is roughly 1400px of
content in an 800–1900px viewport, so watching a run meant scrolling up and down between "which
engine is running", "what is it thinking" and "what has it produced" — and whichever one you
were not looking at was the one that changed.

Two structural problems underneath the scrolling:

1. **Two progress indicators for one run.** The phase rail (Interpreting → Grounding → …) and
   the harness pipeline (Pre-Check → Capability Manager → …) told the same story at different
   granularities. Only one of them can be the truth, and it is the harness.
2. **Every engine had equal weight** even though exactly one matters at a time, and the ones
   that had finished only needed to leave a verdict behind.

## The design pass

Four alternatives were drawn in `goal-flow.pen` before anything was built (A Rail + Spotlight,
B Fixed Cockpit, C one-line HUD, D = B stacked for the portrait Family Hub screen), then a
fifth — **E, the Working Column** — which is what shipped. Each was drawn at 1280×800 or
1080×1920 with a notes card recording what it changes, what it costs, and its motion spec. The
same E layout was then drawn a second time with a **vacation goal** to prove the shape is not
meal-specific (see "Goal-agnostic" below).

## What shipped

One column for the *passage of work*, instead of one panel per kind of information:

```
✓ Pre-Check Engine        ready        1.2s   ← receipt: resolved, permanent
✓ Grounding               grounded    59.3s
✓ Planner                 7 steps     71.6s
● Safety Policy Engine ──────────────────┐    ← the ONE focus card, and the live
  │  transcript + the tool calls it is   │      transcript lives INSIDE it
  │  making, right now                   │
○ Task Manager            queued              ← ghost: not yet run
○ Approval                queued
```

- **`GoalBar`** — the goal itself is the page title, with the run clock opposite it and a 3px
  hairline carrying engines-cleared. This replaced the app header *and* the phase rail.
- **`WorkingColumn`** — receipts / focus card / ghosts, all hung off a single spine.
- **`PlanColumn`** — the plan landing row by row into reserved slots, then the plan hero
  (`PlanCard`) with the tiered approvals underneath it.

Deleted as replaced: `ProgressRail`, `AgentStream`, `HarnessPipeline`, `Skeleton`, `PairedBar`.
Transcript helpers moved to `lib/reasoning.ts`.

## The page never scrolls — and the boxes fit what they hold

The first cut made the focus card absorb every spare pixel, so the column's total height was
invariant from the first beat to the last. Mathematically neat, visually wrong: the device
often has only a line or two to show (see "How little the device actually says"), and that line
sat alone in a box half the height of the screen.

The rule now is **fit the content, cap the growth**: the focus card grows with what it has to
say, its transcript scrolls at its own cap (`max-height: 34vh`), the run column is capped at
62% of the column, and the outcome region takes whatever is left. The page still never scrolls
— that guarantee comes from the caps, not from one element swallowing the slack (verified:
`document.body.scrollHeight > window.innerHeight` is false in every state at 1080×1920).

Measured on a live run: with a one-line note the focus card is **118px** (was ~750px); with a
five-line transcript, **287px**; settled, the run column drops to **273px** of receipts and the
plan takes **1461px**.

Two consequences fell out of the same property:

- **The v5 tail problem dissolves structurally.** Safety / Task Manager / Approval resolve in
  the same millisecond they light up because their real work happens earlier in the run (see
  V5_PLAN's follow-up section). In a row-per-engine panel that was a blink; here a 12 ms engine
  still leaves a permanent receipt carrying its verdict. The render floor
  (`HARNESS_ACTIVE_FLOOR_MS`) is now polish rather than the only thing making those engines
  visible.
- **Between beats no engine is lit at all** — the device resolves one and lights the next a
  beat later, and the render floor widens that gap deliberately. The focus card is *borrowed*
  by the next engine up ("up next") rather than vanishing, because losing the only stretchy
  element for a second would make everything below it jump.

## How little the device actually says

Worth knowing before tuning anything else in this area: over a full ~3-minute run the device
streamed **578 bytes** of prose, all of it in one burst at the top of grounding, then nothing
through the tool loop and nothing at all during the planner's single non-streaming call.
Captured off the wire, not inferred.

That is why the transcript looks sparse, and why the JSON fix below **redacts rather than
deletes** — before it, the assembled-context blob was most of what filled the card, so
removing it silently made the agent look like it had stopped thinking. What genuinely carries
the "it is working" signal through the quiet stretch is the tool-call chips inside the focus
card and the engine receipts accumulating above it.

## Durations tell the truth

Receipts carry the engine's measured wall-clock. Two rules keep that honest:

- **Stamped on ARRIVAL, not at paint.** `enqueueHarness` records the time a beat comes off the
  wire. Paint is deliberately paced, so measuring at drain time would play our own render floor
  back to us as if it were the device's work.
- **Under `HARNESS_MIN_TIMED_MS` (100 ms) no duration is printed at all.** The tail engines
  legitimately measure ~0 beat-to-beat; printing "0.0s" next to an engine that did real work is
  a worse lie than printing nothing, so the verdict speaks alone.

A real run therefore reads `Grounding · grounded · 59.3s`, `Planner · 7 steps · 71.6s`,
`Approval · 5 pending · 1.2s` — which says where the time actually goes. That is a better
argument on stage than seven engines all glowing for an identical 550 ms.

## The plan lands one row at a time

The planner is a **single non-streaming call**: the device gets the whole plan back at once and
then emits every `plan_progress` in one tight loop (`foreach (var item in modelPlan.Plan)`), so
all N frames arrive in the same millisecond, *after* the safety and approval beats.

`PLAN_ITEM_STEP_MS` (320 ms) paces the **reveal** only — the same trick as the harness render
floor. Nothing is invented and nothing is withheld: every row shown is final and has already
cleared the safety gate. Rows land into slots that were reserved before their content existed,
so the region never reflows.

**Contract addition — `plan_progress.total`** (see `CONTRACT.md`). The slot count has to be
exact for a goal of *any* shape, and nothing on the wire said how many items were coming: seven
dinners is a guessable horizon, eleven vacation steps is not. The device knows the count before
it emits the first item, so now it sends it with every one. Optional by design — absent on
pre-v5.1 devices, and a consumer must read that as **unknown, not zero** (the chat UI falls
back to the plan's own length, then to a single placeholder). Mirrored in `CONTRACT.md`,
`contract.py`, `AgentEvent.cs`, both UIs' `contract.ts`; Tizen re-synced.

## Goal-agnostic

The contract was already domain-neutral (`PlanItem {id, title, detail, when?, day, why[],
tags[]}`, `impact: ImpactBadge[]`). The rendering rules are what had to be right:

- **Left column** = the item's `when` if it has one, else its step number. Meals get
  "Tue, Jul 28", a vacation gets "18 Aug", an undated goal gets "03". Never a hardcoded weekday.
- **Headline** is "THE PLAN", never "THE WEEK" — the goal's own words are already in the goal
  bar and the outcome region does not restate the domain.
- **Metrics** are `impact[]` label/value pairs, whatever the planner returned — never a budget
  widget. Empty impact, no row.

Proved by drawing the identical layout with *"Plan our October trip to Kerala"*: only the copy
changed, no structure. One thing that layout surfaces and the system does not yet answer: some
steps have no capability behind them ("arrange a cat sitter" is a task for the human, not an
action for the agent), and a `PlanItem` with no matching proposal does not say which it is.

## The transcript stopped rendering JSON

The grounding model narrates and then dumps the structured context it assembled into the **same
token stream**. The original defence tested each streamed `thinking` fragment for a leading
brace and dropped it — but the device streams token chunk by token chunk, so that deleted
precisely the chunks carrying the braces and kept everything between them. The blob did not
disappear; it reached the stage as mangled pseudo-prose
(`"time_window": "start": "2026-07-28",`), which is worse than either showing it or hiding it.

A blob can only be recognised once the text is **whole**. Fragments now accumulate verbatim
(the raw stream stays intact for the presenter feed) and `stripJsonBlobs` redacts balanced JSON
at render time: string-literal aware, so a `}` inside a quoted value cannot close a blob early,
and an unterminated blob — one still arriving — is cut to the end.

**Redacted, not deleted.** Each blob is replaced by one marker line describing it from its own
contents — `⟨context · time_window, family, hard_constraints⟩`, or `⟨context · 7 items⟩`, or
plain `⟨context⟩` when it will not parse (models emit near-JSON). Nothing is inferred or
invented, and the reader can see that context WAS gathered instead of watching the card sit
empty. Adjacent markers left by one blob collapse to the most informative. Gate:
`npx tsx verify/transcript.check.mts` (8 cases, including the exact observed failure and one
asserting ordinary prose survives byte-identical).

## Verification

Live, against the real device and cloud (no mocks), at 1080×1920:

- receipts with true timings (`grounding 59.3s`, `planner 71.6s`), the focus card streaming its
  transcript, ghosts below;
- the paced reveal caught mid-flight at **"5 of 7 placed"**, and after the contract addition at
  **"1 of 7 placed" with six reserved slots on the very first frame** (device log:
  `agent_event plan_progress seq=1208 item=Spinach Dal Rice Bowl of 7`);
- the settled state with the plan hero and approvals, page scroll false throughout;
- a second goal ("get the house ready for my parents visiting") to exercise a non-meal domain.

Gates: `verify_mirrors` PASS (26 frame types, 7 agent_event kinds), device `verify/m0/check.sh`
PASS, `verify/transcript.check.mts` PASS, both UIs typecheck and build, Tizen builds clean.

## Rejected alternatives

- **Keeping the phase rail alongside the harness.** Two progress bars for one run; the rail is
  the coarser and less true of the two.
- **Per-fragment JSON filtering** (what v5 had). Cannot work: the unit of the stream is a token
  chunk, not a value.
- **Actually streaming the planner** so items arrive one by one for real. It would mean parsing
  partial JSON, and items would appear *before* the safety gate runs — which contradicts "LLM
  plans, code checks". Pacing the reveal of already-screened items keeps the guarantee.
- **Options A–D** (`goal-flow.pen`): A keeps the scroll once the transcript grows; B is right
  but landscape-shaped; C demotes the harness behind a tap, which is the wrong trade on stage;
  D is E's parent and stacks fixed panels instead of conserving height.

## Still open

- Device `planner_notice:` text is emitted as a `thinking` fragment and glues onto the prose
  with no separator (`…finalized planplanner_notice: compose attempt 1/3…`). Cosmetic, device-side.
- The board's `HarnessRibbon` still uses the v5 pipeline styling; only the chat surface moved to
  the working column.
- A `PlanItem` with no proposal behind it should read as "yours to do" rather than implying the
  agent will act.
