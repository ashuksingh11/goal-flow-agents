# Best demo choreography

## Scene 1 — iPad: User gives goal

User says on iPad:

> Help my family eat healthier next week and reduce food wastage.

iPad shows:

```
Goal detected:
Healthier family meals + less food waste
```

Cloud Agent asks:

```
Should I focus on weekday dinners, use existing fridge items first, reduce processed food, and keep busy days lighter?
```

User says:

```
Yes, weekdays only.
```

---

## Scene 2 — iPad: Cloud prepares handoff

iPad shows a beautiful handoff card:

```
Goal confirmed

Sending task to Family Hub Agent...
```

Then show:

```
Cloud Agent → Family Hub Agent
```

This is the first wow moment.

---

## Scene 3 — Family Hub wakes up

Family Hub screen changes from idle to active.

```
New family goal received

Healthier Week + Less Food Waste
Device Agent is checking home context...
```

Then show progress:

```
Checking fridge inventory
Checking expiry dates
Checking family calendar
Checking shopping list
Finding recipe options
Optimizing meal plan
```

This makes the device feel alive.

---

## Scene 4 — Family Hub shows device-side intelligence

Use 4 beautiful cards:

```
Fridge Inventory
Spinach expires in 2 days
Yogurt expires in 3 days
Carrots available
Paneer available
```

```
Calendar
Wednesday is busy
Football practice at 6 PM
Prefer quick/prep-ahead dinner
```

```
Family Preferences
Avoid mushrooms
Avoid pork
Prefer vegetarian weekday dinners
```

```
Planning Goals
Use expiring food first
Increase vegetables
Maintain protein
Reduce processed food
Minimize new groceries
```

This is where people understand the device agent is doing real work.

---

## Scene 5 — Family Hub builds the plan

Instead of instantly showing the final meal plan, show it being built:

```
Monday selected:
Spinach dal rice bowl
Reason: Uses spinach before expiry + adds protein
```

```
Wednesday adjusted:
Lentil soup + toast
Reason: Football practice day, easy to prep early
```

This gives the feeling of reasoning.

---

## Scene 6 — iPad receives final plan

iPad shows:

```
Family Hub created your weekday meal plan.
```

Then final plan appears.

Below the plan, show impact badges:

```
4 fridge items used before expiry
5 vegetable-forward dinners
3 quick-prep meals
0 mushroom/pork meals
Only 4 grocery items needed
```

This is very important for UX impact.

---

## Scene 7 — iPad approval

iPad asks:

```
Approve adding missing items to shopping list?

Lentils
Bell peppers
Curd
Whole wheat bread
```

Buttons:

```
Approve
Edit
Skip
```

Family Hub at the same time shows:

```
Plan ready
Waiting for approval on iPad
```

---

## Scene 8 — Family Hub executes

User taps approve on iPad.

Family Hub changes to:

```
Updating shopping list...
Creating prep reminder...
Saving meal plan...
```

Then:

```
Done

Shopping list updated
Prep reminder created
Meal plan saved
```

This gives very clear device-cloud-device loop.

---

## Scene 9 — Long-running goal state

iPad shows:

```
Your goal is active for next week.
```

Family Hub shows:

```
Monitoring this goal

Inventory changes
Calendar conflicts
Prep reminders
Shopping list status
```

This proves it is a long-running operation, not one chat answer.

---

## Scene 10 — Mid-week adaptation

Simulate Tuesday.

Family Hub detects:

```
Calendar update found
Wednesday football practice may affect dinner prep
```

iPad gets notification:

```
Wednesday looks busy because of football practice.

Should I add a prep reminder for Tuesday 7 PM so dinner takes only 15 minutes tomorrow?
```

User approves.

Family Hub shows:

```
Prep reminder created
Tuesday 7 PM
Soak lentils and chop vegetables
```

This is the strongest demo moment.

---

# Final UX architecture

```
User
 ↓
iPad UI Client
 ↓
Cloud Agent
 ↓
Family Hub Device Agent
 ↓
Family Hub Progress UI + Device APIs
```

The Family Hub UI is not the main app.

It is a **device-side live execution surface**.

---

# Best naming for screens

I would name the iPad view:

**Goal Control Center**

And Family Hub view:

**Home Agent Activity**

Example:

```
iPad:
Goal Control Center
"Healthier Week + Less Food Waste"

Family Hub:
Home Agent Activity
"Family Hub Agent is checking your kitchen context"
```