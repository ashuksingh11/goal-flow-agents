# What “harness” should mean

For your POC, I would define harness like this:

> A harness is the controlled execution layer around the agent that makes the agent reliable, safe, observable, and product-ready.

This is important.

The LLM should not directly do everything. The harness should control:

- what data is fetched
- what actions are allowed
- what needs approval
- what state is stored
- what happens on failure
- how outputs are validated

That is your IP.

---

# Device Agent harnesses I recommend

## 1. Task Lifecycle Harness

Manages the long-running task.

States:

```
CREATED
CONTEXT_COLLECTING
PLANNING
WAITING_FOR_APPROVAL
APPROVED
EXECUTING
MONITORING
ADAPTING
COMPLETED
FAILED
CANCELLED
```

This is mandatory. Without this, long-running goals become messy.

---

## 2. Capability Discovery Harness

Finds what the device can currently do.

Example:

```
{
  "inventory_read": true,
  "expiry_read": true,
  "calendar_read": true,
  "shopping_list_write": true,
  "reminder_write": true,
  "recipe_search": true,
  "grocery_ordering": false
}
```

This lets the agent adapt.

If calendar is unavailable, it should say:

> I can still create the meal plan, but I could not optimize for busy evenings.

---

## 3. Permission + Pre-check Harness

Checks access before planning.

It should validate:

- Can inventory be read?
- Can shopping list be updated?
- Can reminders be created?
- Is calendar connected?
- Is the user authenticated?
- Is network available?
- Is the goal time window valid?

This prevents demo failure.

---

## 4. Context Collection Harness

Collects all relevant context into one normalized object.

Sources:

- inventory
- expiry
- calendar
- shopping list
- previous meals
- family preferences
- health constraints
- existing reminders

Output should be deterministic.

Example:

```
{
  "near_expiry_items": ["spinach", "yogurt", "carrots"],
  "busy_days": ["Wednesday"],
  "avoid_items": ["mushrooms", "pork"],
  "available_proteins": ["paneer", "lentils", "chickpeas"],
  "missing_staples": ["bell peppers"]
}
```

---

## 5. Goal-to-Action Compiler Harness

This is a very important IP layer.

It converts vague goals into measurable operating rules.

Example:

User goal:

> Eat healthier and reduce wastage.

Compiled rules:

```
{
  "increase_vegetables": "at least 1 vegetable-heavy dinner daily",
  "reduce_processed_food": "avoid packaged/ready-to-eat dinners",
  "maintain_protein": "include protein source in every dinner",
  "reduce_waste": "prioritize items expiring within 3 days",
  "schedule_fit": "busy days should have prep time under 25 minutes"
}
```

This is where your POC becomes more than a chatbot.

---

## 6. Meal Candidate Generator Harness

Generates multiple candidate meals per day.

Example:

Monday candidates:

- spinach dal rice bowl
- spinach paneer paratha
- spinach chickpea curry

Then the optimizer chooses.

This prevents the agent from making a random plan.

---

## 7. Optimization + Scoring Harness

Scores each meal.

Suggested scoring:

```
Waste reduction score: 30%
Health score: 25%
Family preference score: 20%
Cooking time score: 15%
Shopping minimization score: 10%
```

Example:

```
{
  "meal": "Spinach dal rice bowl",
  "waste_score": 9,
  "health_score": 8,
  "preference_score": 8,
  "prep_score": 7,
  "shopping_score": 9,
  "total_score": 8.3
}
```

This is demo-friendly because you can show “why” the agent chose something.

---

## 8. Safety + Health Policy Harness

Important if diabetes, weight loss, allergies, child nutrition are involved.

For POC, keep it basic:

- Do not claim medical advice.
- Respect allergies strictly.
- Treat diabetes/weight loss as dietary preferences unless medically verified.
- Escalate risky goals.

Example:

If user says:

> Make meals for my diabetic father.

Agent should say:

> I can create lower-sugar, balanced meal suggestions, but this should not replace medical nutrition advice.

For demo, use simple health rules only.

---

## 9. Approval Policy Harness

Decides what needs user approval.

No approval needed:

- draft meal plan
- read inventory
- read calendar
- suggest reminders

Approval needed:

- add shopping list items
- create reminders
- create to-dos
- order groceries
- change existing calendar/task
- share information externally

This harness is very important for trust.

---

## 10. Action Execution Harness

Executes only approved actions.

Actions:

```
[
  {
    "type": "ADD_TO_SHOPPING_LIST",
    "items": ["paneer", "lentils", "bell peppers"]
  },
  {
    "type": "CREATE_REMINDER",
    "title": "Soak lentils for Wednesday dinner",
    "time": "Tuesday 7 PM"
  }
]
```

It should also return execution status:

```
{
  "shopping_list_update": "success",
  "reminder_creation": "success"
}
```

---

## 11. Event Monitoring Harness

This powers the long-running nature.

Monitors:

- calendar changes
- inventory changes
- near-expiry alerts
- missed prep reminders
- shopping list not completed
- plan not started

For POC, only monitor one thing:

**Calendar change / busy day conflict.**

Don’t build too much.

---

## 12. Adaptation Harness

When something changes, this harness decides whether to adapt.

Example:

```
Wednesday football match found.
Dinner prep time is 45 minutes.
Recommended action: move prep to Tuesday evening.
Approval required: yes.
```

This creates the wow moment.

---

## 13. Explanation Harness

Very important for UX.

Every plan should answer:

- Why this meal?
- What inventory does it use?
- What health goal does it support?
- What does it avoid?
- What action is needed?

Example:

> I picked spinach dal on Monday because spinach expires soon, dal adds protein, and it avoids processed ingredients.

This makes the agent feel intelligent.

---

## 14. Failure Recovery Harness

For demo reliability.

Examples:

- Inventory unavailable → use mock inventory.
- Calendar unavailable → skip schedule optimization.
- Recipe API fails → use cached recipes.
- Shopping list update fails → show retry.

For POC, this is critical.

The demo should not collapse because one API is unavailable.

---

## 15. Audit + Trace Harness

This is useful for architecture demo.

Track:

- user goal
- retrieved context
- compiled constraints
- device capabilities used
- plan generated
- approval requested
- action executed
- final status

This allows you to show a backend trace:

```
Goal received → ambiguity resolved → device task created → inventory read → plan optimized → approval received → shopping list updated → reminder created
```

This will impress technical reviewers.

---

# The strongest IP harnesses

If you want to showcase IP, focus on these 5:

## 1. Goal-to-Action Compiler

Turns vague goals into measurable execution rules.

## 2. Capability-Aware Planner

Plans based on what the device can actually do right now.

## 3. Approval Policy Engine

Separates suggestion from execution.

## 4. Context Optimizer

Balances inventory, health, family preference, and calendar.

## 5. Long-running Adaptation Engine

Keeps the goal alive after the first answer.

These five are the heart of the POC.