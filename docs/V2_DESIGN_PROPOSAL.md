# GoalFlow v2 — Design Proposal (general goal-based agent)

Reframes GoalFlow from a meal-planning demo into a **general goal-based agent for the Samsung Family
Hub**, where meal planning is one domain and the reusable orchestration layer — the **harness
modules** — is the star. Derived by first cataloguing goal-based use cases, then extracting the
harnesses that are useful *across* them.

## 1. What the Family Hub can actually do (the substrate)

A Family Hub is a smart fridge + screen + SmartThings home hub. Realistically it can sense/act on:
inventory (interior cameras / Samsung Food), the shared family calendar, shopping list & ordering,
reminders/notes, recipes, **other appliances via SmartThings** (oven, dishwasher, washer, robot
vacuum, lights), family member profiles, notifications/announcements, and a budget. A general agent
plans over *these capabilities* toward *any* goal.

## 2. Goal-based use-case catalog

| # | Goal (what a user says) | Why it's a good agent demo |
|---|---|---|
| 1 | **"Help my family eat healthier this week & cut waste."** (flagship) | Fuzzy goal, real context, HITL, weekly adaptation. |
| 2 | **"We've got 6 people over Saturday for dinner — sort it."** (recommended 2nd demo) | New domain, guest dietary constraints, a prep *timeline*, appliance coordination, a sharp live adaptation (a guest RSVPs a nut allergy / arrives late). |
| 3 | "Help us get through this hectic week." | Reconcile calendars + meals + chores; surface conflicts. Broad but abstract. |
| 4 | "Keep us stocked and under budget on groceries." | Restock + budget guardrail; overlaps meal. |
| 5 | "Make school mornings less chaotic." | Breakfast + lunchbox + calendar + announcements. |
| 6 | "Help Dad stick to his low-sodium diet." | Hard health constraint threaded through everything. |
| 7 | "Keep the house running." | Chores + appliance orchestration via SmartThings, quiet hours. |

**Recommended demo pair: #1 (meal, enriched) + #2 (guest dinner prep).** They share most modules but
feel different, so the *same harness pipeline* visibly handles two goals → proves "general agent, not
a meal app."

## 3. The harness modules (domain-agnostic — the reusable star)

Eleven modules, each with a crisp purpose, how it *steers* the LLM, and the real framework primitive
it's built on. This is the layer that lights up in the presenter view.

| Harness module | Purpose | How it steers the LLM | Built on |
|---|---|---|---|
| **Goal Interpreter** | Fuzzy goal → structured objective, success criteria, constraints, scope. | Forces structure before action. | LangGraph node + LLM (structured output) |
| **Memory & Constraints** | Hard constraints (allergens/medical/budget/child-safety) + soft prefs + episodic memory. | Injects hard truth the LLM may not override; biases with soft prefs. | Store + verbatim injection (hard) / retrieval (soft) |
| **Context Grounding** | Pull current world-state relevant to the goal from capability modules. | Feeds real facts so it doesn't hallucinate state. | Assembler over SK plugins |
| **Capability Registry** | The toolbox the planner may use; enables new domains/modules. | Scopes the action space to what the Hub can actually do. | SK plugin/function discovery |
| **Planner** | Produce the plan + proposed actions. | The reasoning engine. | **SK auto function-calling** over capability modules |
| **Safety & Policy Filter** | Block actions violating hard rules (allergen, budget cap, quiet hours, unattended appliance). | Vetoes unsafe LLM tool calls — **"LLM plans, code checks."** | **SK `IFunctionInvocationFilter`** |
| **Approval / Consent (HITL)** | Tier actions by reversibility × cost × risk; pause for consent on costly/irreversible ones. | Inserts the human at the right moments. | **LangGraph `interrupt()`** + filter |
| **Actuator / Effect Executor** | Perform approved actions once, record outcomes. | Makes effects idempotent & safe. | Idempotent executor over SK plugins |
| **Scheduler / Temporal** | Time-based actions & prep timelines off a generic clock. | Sequences work over time. | Clock abstraction (real/simulated) |
| **Monitor & Adapt** | Detect *material* world changes; re-plan only the affected slice. | Keeps behavior correct as the world changes. | Change watcher + materiality policy |
| **Trace / Explain** | Per-decision rationale + structured, correlation-id logs. | Observability + the presenter feed + **debuggability**. | Structured logging + SK/LG hooks |

**Not every goal uses every module** — the pipeline is composed from the registry per goal. Named
extension points (not built now): Budget module, Quiet-Hours module, Multi-user consent.

## 4. Capability modules (domain tools — SK plugins the LLM calls)

- **Home/shared:** Calendar, Reminders, Notify/Announce, FamilyProfiles, **ApplianceControl
  (SmartThings)**, ShoppingList/Order, Budget.
- **Meal domain:** Inventory, Recipes.
- **Guest-prep domain:** Guests/RSVP — and it *reuses* Calendar, Reminders, ApplianceControl,
  Shopping, Recipes, FamilyProfiles.

Each is an SK plugin exposing `KernelFunction`s (e.g. `Inventory.GetExpiringItems`,
`ShoppingList.Add`, `Appliance.PreheatOven`, `Reminders.Create`). The LLM *calls* these; the Safety
filter can veto any call.

## 5. Enriched meal-planning flow (more steps / approvals / branches)

Beyond "plan → approve list → adapt," add:

- **Tiered approvals** (reversibility × cost × risk): auto-do reversible (set a reminder); *light*
  approval (add to shopping list); *firm* approval (**place the grocery order — spends money**);
  *adapt* approval (change the plan).
- **Budget guardrail:** estimate grocery cost; the Safety filter blocks an order over the cap; ask to
  approve the spend.
- **Leftover-rescue branch:** an item about to expire → propose using it tonight (waste win).
- **Appliance assist:** "defrost the paneer tonight" / "preheat oven at 18:30" via ApplianceControl.
- **Preference conflict:** two members' prefs clash → surface for a quick choice.

## 6. How the demo proves generality

Run goal #1 (meal) and goal #2 (guest prep) through the **same 11 harness modules**. The presenter
view shows the identical harness pipeline lighting up for a completely different goal with a
different capability-module set. That is the thesis made visible: **a general goal agent + pluggable
Family-Hub modules**, not a meal app.

## Decisions locked (confirmed)

- **Demo pair:** enriched meal planning + **guest dinner prep** ("6 over Saturday"). Other domains later.
- **Architecture:** native SK (plugins + auto function-calling + `IFunctionInvocationFilter`) on the
  device; advanced LangGraph (StateGraph + conditional edges + `interrupt()` HITL + checkpointer) on
  the cloud. Harnesses stay as the star, expressed as real modules/primitives.
- **LLM-only planning** (no rules/scripted planners, no fallbacks); harness modules steer/guard.
- **Ground-up wow UI**; **generic dates** (relative to real today) + fix day-advance bug; **structured
  logging** in both agents.
- **Device stays Tizen-lean:** only Semantic Kernel + BCL (`System.Net.WebSockets`, `System.Text.Json`)
  + minimal `Microsoft.Extensions.*`. No fancy/native/desktop libraries. SK runtime-on-Hub = the open
  spike for the user's manual Tizen test.

## 7. What changes vs v1 (the rebuild)

- **LLM-only** planning (remove rules/scripted planners + fallbacks). Harness modules steer/guard.
- **SK plugins + auto function-calling** (device APIs become tools the LLM calls) + **SK filter** for
  safety.
- **Advanced LangGraph** StateGraph: conditional edges, **`interrupt()`-based HITL**, a checkpointer
  for durable state across the approval pause.
- **Generic dates** (derive the week from the real current date / configurable start) + fix the
  day-advance UI bug.
- **Structured logging** in both agents (leveled, correlation-id tagged).
- **Ground-up wow UI** (streaming thoughts/tool-calls, progress rail, skeleton loaders, motion,
  minimal text, plan-as-hero).
- **Domain-agnostic core** + meal & guest-prep module sets.
