# V6 — Constraints With Provenance ("where did this rule come from?")

## Why

GoalFlow's whole claim is *"LLM plans, code checks."* The thing the code checks is
`constraints.hard` — and until v6 that block was **seeded once, by hand, in the shape of a
meal**:

```jsonc
// goal-flow-cloud-agent/data/memory/family_profile.json — the v5 state
"hard": { "allergens": ["peanuts"], "medical": ["rohan_low_sodium"], "dietary": ["no_pork"],
          "budget_cap": 120.0, "quiet_hours": { "start": "21:30", "end": "07:00" } },
"soft": { "dislikes": ["mushrooms"], "prefer": ["more_vegetables", ...],
          "habits": ["vegetarian_weekday_dinners", "grocery_run_saturday_morning"] }
```

Three problems, in order of how much they cost the demo:

1. **Every goal gets the meal household.** A `vacation_prep` goal is dispatched with a
   **weekly grocery cap of $120** — as the ceiling on a trip — and a planning bias that
   prefers more vegetables and dislikes mushrooms. v3.5 made the *planner* generic per
   domain; the *constraints* it plans against never followed.
2. **Only the meal domains have a constraint that can actually fire.** Allergens and
   dietary terms block an ingredient list. Vacation, energy and grocery-cost goals reach
   the Safety filter with nothing that can bind, so the gate is real for two use cases out
   of six and decorative for the rest.
3. **The same household truth exists twice, hand-synced, with no provenance on either
   copy.** `budget_cap: 120` is policy in the cloud profile and *also* `cap: 120` in the
   device's `data/budget.json`; Rohan's low-sodium is a hard constraint in the cloud and a
   restated note in `data/family.json`. Nothing anywhere records **where a constraint came
   from**, which is the question a real product has to answer before it is allowed to
   block a user.

v6 makes constraints a **first-class, sourced, scoped, expiring model** that resolves
*per goal* — so a vacation goal is constrained like a vacation, and every constraint can
say who set it and when it stops applying.

## The rules this design is built on

Settled up front, because each one closes off a tempting-but-wrong implementation:

| # | Rule | Why |
|---|---|---|
| R1 | Every constraint carries a **`source`**: `account` (user entered it), `derived` (real-world data — tariff, calendar, receipts), `chat` (the user said it). | Provenance is the feature. A block the user can't trace is a block they won't trust. |
| R2 | **The LLM never authors a hard constraint.** Chat capture proposes; the user confirms; only then does it enforce. | Letting the model write the policy it is checked against collapses the split the whole architecture rests on. |
| R3 | **Policy pushes down; facts are discovered up.** The account is the source of truth for constraints; the device owns world state (`spent`, inventory, appliance draw) and receives policy on the dispatch. | Removes the duplication. `budget.json` should report the cap it was *dispatched*, not restate it. |
| R4 | Constraints have **`scope`** (household / domain / goal) and **expiry**. | "$1500 travel" is per-trip, not household policy; "Aarav on antibiotics, 10 days" retires itself. |
| R5 | Enforcement is **household-flat** — no per-member binding. | Member binding makes "who is attending" (an LLM judgement) an input to safety. Not worth it. |
| R6 | A goal may **tighten** a constraint, never loosen or remove one. | Deterministic, cheap, and it stops "actually Rohan's sodium thing is fine now" from relaxing a medical constraint by phrasing. |
| R7 | **The enforced set is never narrowed by relevance.** Domain selection picks which *cap/window* applies and what *bias* is sent — allergens ride along on every goal. | A wrong relevance pick must cost a noisy plan, never a safety miss. |

## What

### The constraint store (cloud, account-side)

`family_profile.json` becomes a **library of constraint entries**, one per *fact* (not one
per kind) so each carries its own provenance and lifetime:

```jsonc
{
  "family_id": "family-hub-demo",
  "members": [ ... ],
  "constraints": [
    { "id": "c-allergen-peanuts", "kind": "allergens", "value": ["peanuts"],
      "enforcement": "hard", "source": "account", "scope": "household",
      "applies_to": ["*"], "note": "Aarav — entered in the Family Hub profile" },

    { "id": "c-cap-groceries", "kind": "budget_cap", "value": 120.0, "period": "weekly",
      "enforcement": "hard", "source": "derived", "scope": "domain",
      "applies_to": ["meal_plan", "grocery_cost", "guest_dinner"] },
    { "id": "c-cap-party",  "kind": "budget_cap", "value": 200.0,
      "applies_to": ["birthday_party"], "...": "..." },
    { "id": "c-cap-travel", "kind": "budget_cap", "value": 1500.0,
      "applies_to": ["vacation_prep"], "...": "..." },

    { "id": "c-peak-tariff", "kind": "peak_hours", "value": { "start": "17:00", "end": "21:00" },
      "enforcement": "hard", "source": "derived", "scope": "domain",
      "applies_to": ["energy_saving"], "note": "utility tariff — peak rate window" },

    { "id": "c-away", "kind": "away_window",
      "value": { "start_day_offset": 1, "end_day_offset": 8 },
      "enforcement": "hard", "source": "derived", "scope": "household",
      "applies_to": ["*"], "expires_day_offset": 8,
      "note": "shared calendar — the family is away" },

    { "id": "s-no-mushrooms", "kind": "dislikes", "value": ["mushrooms"],
      "enforcement": "soft", "source": "account", "scope": "household",
      "applies_to": ["meal_plan", "guest_dinner", "grocery_cost"] }
  ]
}
```

Dates are **day offsets resolved against today at load**, matching the device's
generic-clock rule — absolute dates go stale between demos.

### Resolution — `resolve(domain, today)`

Deterministic, in code, for everything hard (R2, R7):

- **List kinds** (`allergens`, `dietary`, `medical`) — **union of every entry**, regardless
  of domain. Never narrowed.
- **Scalar kinds** (`budget_cap`, `quiet_hours`, `peak_hours`, `away_window`) — most
  specific `applies_to` wins; on a tie, the **stricter** value wins.
- **Expired entries** are dropped before either step.

Soft bias is picked by a **small structured LLM call** in `load_memory` (objective +
domain + candidate ids → relevant ids), with `applies_to` tag-matching as the fallback when
the call fails *or* when the interpreter coined a domain slug nobody tagged. Soft can be
wrong for free; hard cannot, which is exactly why only soft goes near the model.

### What each domain is actually constrained by

The point of the whole exercise — meal and vacation stop looking alike:

| Domain | Hard (enforced) | Soft (bias) |
|---|---|---|
| `meal_plan` | allergens · dietary · medical · **grocery cap $120** · quiet hours | dislikes, weekday-vegetarian, prefer-vegetables |
| `guest_dinner` | allergens · dietary · medical · grocery cap · **quiet hours** (dishwasher) | hosting style, guest diets |
| `vacation_prep` | allergens · dietary · medical · **travel cap $1500** · **away window** | hold deliveries, eco while away, use up perishables |
| `birthday_party` | allergens · dietary · medical · **party cap $200** | hosting style, kid-friendly |
| `grocery_cost` | allergens · dietary · medical · **grocery cap** | prefer substitutions, bulk staples |
| `energy_saving` | **peak tariff window** · quiet hours | prefer eco programs, off-peak shifting |

Two of these are **new enforcement**, and they are deliberately the ones that make a
vacation goal feel different from a meal goal:

- **`peak_hours`** needs **no new device code** — it is the existing `time_window_block`
  rule kind with a new instance in `policy.json`. Scoped to `energy_saving` on purpose: a
  peak-hour dishwasher run defeats *that goal's own objective*, whereas blocking it
  household-wide would break the guest-dinner cleanup beat for no safety reason.
- **`away_window`** needs one **new rule kind** (a date-range variant of the window block):
  an appliance run, delivery or announcement scheduled into an empty house is **blocked**,
  not merely discouraged.

  **Scoped to `vacation_prep`, not `["*"]` — and that is a limit, not the design.** The
  honest rule is household-wide: the window is self-limiting (it only fires when a call
  carries a date inside it), so it would also catch a *meal* goal preheating the oven
  mid-trip, which is the better bug to catch. It is scoped down because **the seeded world
  contradicts itself**: `energy.json` has the meal domain filling days 1–6 while
  `vacation.json` has the family away days 1–8. Nothing cross-checks those today, so the
  inconsistency is invisible — until an enforced away window starts blocking the meal
  demo's appliance proposals. Widening this to `["*"]` is a **world-data fix first**
  (move the trip off the meal week), then a one-word change in the store.

### Household envelope (M3)

The cap is policy; the **spend is world state**. `budget.json` keeps `spent` and loses
`cap` (R3), so:

```
effective cap = min(domain cap, monthly envelope − spent)
```

resolved into the armed policy at `BeginGoal`, and **re-resolved on approval and on the day
tick**. That re-resolution is the cross-goal beat: approving the party order shrinks the
grocery goal's headroom and drives it through its existing adapt path.

**The rule engine's invariant survives.** `SafetyRule` docs promise *"rules read
`constraints.hard` and nothing else."* The envelope arithmetic happens in a **policy
resolution step** before arming, not inside a rule — so rules stay pure and the armed block
stays the single input.

### Chat capture (M4)

"We've gone vegan" is **captured, never silently enforced** (R2). The cloud proposes the
constraint; the user confirms; it persists with `source: "chat"`, a scope, and an optional
expiry. The proposal rides on the **existing understanding gate** as additive payload
fields rather than a new frame kind — that card is already a confirmation surface. The
goal-less utterance ("we've gone vegan", no goal attached) needs its own reply path, since
the interpreter declines it as non-actionable today.

## How (contract delta)

`constraints.hard` gains three explicit keys. `HardConstraints` already allows extra keys,
but the mirrors get them by name so the shape is documented and gated:

```jsonc
"hard": {
  "allergens": [], "medical": [], "dietary": [],
  "budget_cap": null,                                   // now domain-resolved
  "quiet_hours": { "start": "21:30", "end": "07:00" },
  "peak_hours":  { "start": "17:00", "end": "21:00" },  // NEW (M1/M2)
  "away_window": { "start": "<ISO>", "end": "<ISO>" },  // NEW (M1/M2)
  "budget_envelope": { "cap": 600.0, "period": "monthly" }  // NEW (M3)
}
```

Additive on `understanding` (M1, ignorable until the UI adopts it in M4):

```jsonc
"constraints": [ { "id": "c-cap-travel", "label": "travel budget", "value": "$1500",
                   "source": "account", "why": "vacation_prep" } ]
```

`knew` stays exactly as it is, so no UI change is required to ship M1–M3.

Mirrors to update: `goal-flow-cloud-agent/CONTRACT.md` + `models/contract.py`, both UIs'
`src/types/contract.ts`, and `Contracts/Dispatch.cs` (hard is a free-form `JsonObject`
there, so the C# change is documentation, not structure). Gated by
`scripts/verify_mirrors.py`.

## Milestones

**M1 — Constraint model with provenance (cloud only) — ✅ SHIPPED**
Constraint library + `resolve_constraints(domain, today, soft_ids)` + soft relevance pass in
`load_memory`; contract mirrors; `_hard_knew` picks up the resolved values for free.
*Gate:* `scripts/verify_constraints.py` (gate 15) — a `vacation_prep` goal dispatches the
**travel cap and away window** and carries **zero** mushroom/vegetable bias; a `meal_plan`
dispatch is byte-identical to v5; a **coined** domain still gets the full enforced set plus
the household default cap.

Two things M1 learned that the design did not predict:

- **The relevance pass was budgeted at 200 tokens and silently never ran.** The default
  model is a reasoning model, so its thinking consumed the allowance, the structured call
  returned `None` with no exception, and every goal fell through to tag matching — the
  fallback working perfectly is exactly what hid it. Raised to 1200; the empty case now
  logs. A pass that quietly never runs is worse than not having one.
- **The tie-break needed a rule.** Two equally-specific caps is a store-authoring bug, but
  it has to resolve *somewhere*: numbers go to the stricter (lower) value, windows keep the
  incumbent and log, because two windows do not order meaningfully.

**M2 — Enforcement parity + de-dup (device + Tizen)**
`peak_hours` rule instance in `policy.json`; new date-window rule kind for `away_window`;
`BudgetPlugin.GetBudgetStatus` reports the **dispatched** cap via a `SafetyFilter` accessor;
`budget.json` drops `cap`, `family.json` drops its restated medical note; check whether
`vacation.json.away` should follow the same path (it is currently read only into the
observer's world snapshot). Tizen re-sync per the usual recipe.
*Gate:* a dishwasher run scheduled inside the away window is **blocked and explained**; a
heavy run inside the peak window is blocked on an energy goal and allowed on a guest dinner.

**M3 — Household envelope (cross-goal)**
Envelope constraint, effective-cap resolution at arm time, re-resolution on approval and day
tick.
*Gate:* two live goals; approving one's order shrinks the other's headroom and the other
re-plans.

**M4 — Chat capture beat**
Capture → confirm → persist with `source: chat`; goal-less capture path; chat UI renders
provenance on the understanding card.
*Gate:* a constraint captured in chat enforces on the **next** goal, and the block cites
where it came from.

## Where (files)

- **Cloud:** `data/memory/family_profile.json` (→ constraint library), `memory/store.py`
  (resolution), `graph/nodes.py` (`load_memory`, `build_contract`, `_hard_knew`),
  `models/contract.py`, `CONTRACT.md`.
- **Device (Ubuntu + Tizen):** `Products/FamilyHub/config/policy.json` (rule instances),
  `Harness/SafetyPolicyEngine/SafetyRule.cs` (date-window kind),
  `Harness/SafetyPolicyEngine/SafetyFilter.cs` (armed-policy accessor, envelope resolution),
  `Products/FamilyHub/Plugins/BudgetPlugin.cs`, `data/budget.json`, `data/family.json`.
- **UIs:** none until M4 (`knew` chips are already generic over keys).

## Branching

A `v6` integration branch per touched repo, milestone branches off it
(`v6-m1-constraint-model`, …), merged back with `--no-ff` when the milestone's gate passes.
Push only `v6` and `master`. Tag `pre-v6` on master before the eventual merge.
