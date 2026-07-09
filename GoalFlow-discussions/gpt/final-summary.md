# Goal-Based Agent POC Summary

## Samsung Family Hub + Cloud Agent + Device Agent

## 1. POC Context

We are building a proof of concept for **goal-based agents** involving:

- A **Cloud Agent**
    
- A **Device Agent running on Samsung Family Hub**
    
- A **UI client**, likely on an iPad/tablet
    
- A **Family Hub activity UI** that shows what the device-side agent is doing
    

The core idea is that the user gives a **high-level goal**, not a direct command.

Example user prompt:

> Help my family eat healthier next week and reduce food wastage too.

The system should convert this broad goal into a structured, long-running, human-in-the-loop task.

---

## 2. Main POC Use Case

The initial use case is around family meal planning.

The agent should help the family:

- Eat healthier
    
- Reduce food wastage
    
- Use existing fridge inventory first
    
- Respect family preferences
    
- Consider calendar/schedule constraints
    
- Ask for user approval before taking actions
    
- Continue monitoring/adapting during the week
    

Suggested demo scope:

- Weekday dinner planning as the main output
    
- Leftover-aware lunch suggestions as an optional wow layer
    
- Shopping list updates with approval
    
- Prep reminders with approval
    
- One mid-week adaptation based on calendar/schedule change
    

This should not be positioned as just an “AI meal planner.”  
It should be positioned as:

> A goal-based home agent that converts a family wellness goal into a long-running, device-executed plan using inventory, calendar, preferences, approvals, and adaptive follow-through.

---

## 3. High-Level Agent Roles

### Cloud Agent

The Cloud Agent should own:

- User conversation
    
- Goal understanding
    
- Family memory/preferences
    
- Previous conversations
    
- Health goals
    
- Family profiles
    
- Ambiguity detection
    
- Clarification questions
    
- Goal decomposition
    
- Approval flow
    
- User-facing final response
    

The Cloud Agent is the main agent that talks to the user.

### Device Agent / Family Hub Agent

The Device Agent should own:

- Device-side task execution
    
- Checking local/home context
    
- Reading mocked or real inventory
    
- Reading mocked or real calendar
    
- Reading mocked or real shopping list
    
- Recipe/meal planning
    
- Optimization
    
- Action execution after approval
    
- Device-side progress reporting
    
- Long-running monitoring/adaptation
    

The Device Agent should not directly ask the user for approval.  
It should send approval requests to the Cloud Agent, and the Cloud Agent should present them on the iPad/tablet UI.

---

## 4. UX Direction

The preferred UX direction is a **two-screen demo**.

### iPad / Tablet UI

The iPad acts as the **Goal Control Center**.

It should handle:

- User chat
    
- Goal clarification
    
- Goal summary
    
- Approval requests
    
- Final plan
    
- Edit/approve/skip actions
    
- Active goal status
    
- Notifications during the week
    

### Family Hub UI

The Family Hub acts as the **Home Agent Activity Screen**.

It should show what the Device Agent is doing after the Cloud Agent hands off the task.

It should show:

- Task received
    
- Device-side progress
    
- Fridge/inventory check
    
- Calendar check
    
- Preference check
    
- Recipe planning
    
- Meal optimization
    
- Shopping list update status
    
- Reminder creation status
    
- Monitoring/adaptation events
    

The Family Hub should not become another chat screen.  
It should mostly show activity, status, and progress.

---

## 5. Demo Story Flow

### Step 1: User starts on iPad

User opens the chat UI on iPad and says:

> Help my family eat healthier next week and reduce food wastage too.

Cloud Agent identifies this as a high-level family goal.

iPad shows:

- Goal detected
    
- Healthier family meals
    
- Reduce food wastage
    
- Timeframe: next week
    
- Scope needs clarification
    

Cloud Agent asks:

> Should I focus on weekday dinners, use existing fridge items first, reduce processed food, and keep busy days lighter?

User replies:

> Yes, weekdays only.

---

### Step 2: Cloud Agent confirms goal

Cloud Agent creates a structured goal.

Possible structured goal package:

```json
{
  "goal_id": "family_healthier_week_2026_07_13",
  "goal_type": "weekly_family_meal_optimization",
  "primary_objective": "Improve weekday eating quality and reduce food wastage",
  "scope": {
    "meals": ["weekday_dinner"],
    "secondary_outputs": ["leftover_lunch_suggestions", "prep_reminders"],
    "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
  },
  "family_context": {
    "avoid": ["mushrooms", "pork"],
    "preferences": ["vegetarian weekday dinners"],
    "health_goals": ["reduce processed food", "increase vegetables", "maintain protein"]
  },
  "optimization_goals": [
    "use near-expiry inventory first",
    "minimize missing ingredients",
    "avoid disliked foods",
    "fit cooking time to calendar",
    "reuse leftovers for lunch where possible"
  ],
  "approval_policy": {
    "add_to_shopping_list": "requires_user_approval",
    "create_reminder": "requires_user_approval",
    "create_todo": "requires_user_approval",
    "change_existing_plan": "requires_user_approval"
  }
}
```

---

### Step 3: Cloud hands task to Family Hub Device Agent

iPad shows:

> Sending task to Family Hub Agent...

Family Hub wakes up and shows:

> New family goal received  
> Healthier Week + Less Food Waste  
> Device Agent is checking home context...

Family Hub progress should show:

- Checking fridge inventory
    
- Checking expiry dates
    
- Checking family calendar
    
- Checking shopping list
    
- Finding recipe options
    
- Optimizing meal plan
    

---

### Step 4: Family Hub shows device-side intelligence

Family Hub can show clean cards like:

#### Fridge Inventory

- Spinach expires in 2 days
    
- Yogurt expires in 3 days
    
- Carrots available
    
- Paneer available
    

#### Calendar

- Wednesday is busy
    
- Son has football practice at 6 PM
    
- Prefer quick/prep-ahead dinner
    

#### Family Preferences

- Avoid mushrooms
    
- Avoid pork
    
- Prefer vegetarian weekday dinners
    
- Reduce processed food
    

#### Planning Goals

- Use expiring food first
    
- Increase vegetables
    
- Maintain protein
    
- Reduce processed food
    
- Minimize new groceries
    

---

### Step 5: Device Agent builds the plan

Family Hub should show the plan building step by step, not instantly.

Example:

> Monday selected: Spinach dal rice bowl  
> Reason: Uses spinach before expiry + adds protein

> Wednesday adjusted: Lentil soup + toast  
> Reason: Football practice day, easy to prep early

This makes the agent feel like it is reasoning and optimizing.

---

### Step 6: iPad receives final plan

iPad shows:

> Family Hub created your weekday meal plan.

Example plan:

|Day|Dinner|Why|
|---|---|---|
|Monday|Spinach dal rice bowl|Uses spinach before expiry, high protein|
|Tuesday|Paneer veggie wraps|Uses carrots, quick dinner|
|Wednesday|Lentil soup + toast|Light meal for football day|
|Thursday|Chickpea salad bowl|High fiber, low processed|
|Friday|Veg pasta with yogurt dip|Uses remaining vegetables|

Impact badges:

- 4 fridge items used before expiry
    
- 5 vegetable-forward dinners
    
- 3 quick-prep meals
    
- 0 mushroom/pork meals
    
- Only 4 grocery items needed
    

---

### Step 7: User approval

iPad asks:

> Approve adding missing items to shopping list?

Items:

- Lentils
    
- Bell peppers
    
- Curd
    
- Whole wheat bread
    

Actions:

- Approve
    
- Edit
    
- Skip
    

Family Hub simultaneously shows:

> Plan ready  
> Waiting for approval on iPad

After approval, Family Hub shows:

- Updating shopping list
    
- Creating prep reminder
    
- Saving meal plan
    

Then:

> Done  
> Shopping list updated  
> Prep reminder created  
> Meal plan saved

---

### Step 8: Goal becomes active

iPad shows:

> Your goal is active for next week.

Family Hub shows:

> Monitoring this goal

Monitoring examples:

- Inventory changes
    
- Calendar conflicts
    
- Prep reminders
    
- Shopping list status
    

This is important because the demo should show a long-running goal, not a one-time chat response.

---

### Step 9: Mid-week adaptation

For demo, simulate Tuesday.

Family Hub detects:

> Calendar update found  
> Wednesday football practice may affect dinner prep

iPad gets notification:

> Wednesday looks busy because of football practice.  
> Should I add a prep reminder for Tuesday 7 PM so dinner takes only 15 minutes tomorrow?

User approves.

Family Hub shows:

> Prep reminder created  
> Tuesday 7 PM  
> Soak lentils and chop vegetables

This is the strongest agentic moment because it shows:

- Goal is still active
    
- Device Agent is monitoring context
    
- Agent adapts to schedule
    
- User remains in control
    

---

## 6. Important UX Principles

- iPad should be the main user interaction surface.
    
- Family Hub should be the device-side activity surface.
    
- Only iPad should ask approval questions.
    
- Family Hub should show “waiting for approval on iPad.”
    
- Avoid raw technical logs in consumer UX.
    
- Show human-readable agent activity.
    
- Use a presenter/architect mode if technical flow needs to be shown.
    
- The demo should feel like the home system is actively working on a family goal.
    

---

## 7. High-Level Architecture

```text
User
 ↓
iPad / Tablet UI Client
 ↓
Cloud Agent
 ↓
Device Task Gateway
 ↓
Family Hub Device Agent
 ↓
Device Harness Layer
 ↓
Inventory / Calendar / Recipes / Shopping List / Reminders
```

---

## 8. Technology Direction

### Cloud Side

Possible stack:

- Backend: Node.js, Python, or .NET
    
- Agent orchestration: Semantic Kernel or Microsoft Agent Framework
    
- LLM: Azure OpenAI / OpenAI
    
- Memory: Postgres + vector DB
    
- Event store: Postgres / Cosmos DB
    
- Messaging: Azure Service Bus / Kafka / Redis Streams
    
- UI updates: WebSocket / SSE
    

### Device Side

Planned direction:

- Device Agent runs on Samsung Family Hub
    
- Use Microsoft Semantic Kernel
    
- Local task state via SQLite or local JSON store
    
- Device communication via REST/WebSocket/MQTT
    
- Plugins/adapters for:
    
    - Inventory
        
    - Calendar
        
    - Recipes
        
    - Shopping list
        
    - Reminders
        
- Real Samsung Family Hub where possible
    
- Mock inventory, calendar, recipes, and shopping list where real APIs are unavailable
    

Important technical spike:

- Validate whether Semantic Kernel runtime can run cleanly on Samsung Family Hub.
    
- If not, fallback can be a device-side service or simulated device runtime while keeping the demo narrative intact.
    

---

## 9. Harness Concept

A harness is the controlled execution layer around the agent.

It makes the agent:

- Reliable
    
- Safe
    
- Observable
    
- Product-ready
    
- Demo-ready
    

The LLM should not directly execute everything.  
The harness should control:

- What data is fetched
    
- What actions are allowed
    
- What requires approval
    
- What state is stored
    
- What happens on failure
    
- How outputs are validated
    

The harness layer is important because it can become the IP of the POC.

---

## 10. Suggested Device Agent Harnesses

### 1. Task Lifecycle Harness

Manages long-running task state.

Possible states:

```text
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

---

### 2. Capability Discovery Harness

Finds what the Family Hub can currently do.

Example:

```json
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

---

### 3. Permission + Pre-check Harness

Checks whether the device has access to required capabilities.

Examples:

- Can inventory be read?
    
- Can calendar be read?
    
- Can shopping list be updated?
    
- Can reminders be created?
    
- Is the user authenticated?
    
- Is network available?
    

---

### 4. Context Collection Harness

Collects and normalizes relevant context.

Sources:

- Inventory
    
- Expiry dates
    
- Calendar
    
- Shopping list
    
- Previous meals
    
- Family preferences
    
- Health constraints
    
- Existing reminders
    

Example output:

```json
{
  "near_expiry_items": ["spinach", "yogurt", "carrots"],
  "busy_days": ["Wednesday"],
  "avoid_items": ["mushrooms", "pork"],
  "available_proteins": ["paneer", "lentils", "chickpeas"],
  "missing_staples": ["bell peppers"]
}
```

---

### 5. Goal-to-Action Compiler Harness

Converts vague goals into measurable operating rules.

Example:

User goal:

> Eat healthier and reduce wastage.

Compiled rules:

```json
{
  "increase_vegetables": "at least 1 vegetable-heavy dinner daily",
  "reduce_processed_food": "avoid packaged/ready-to-eat dinners",
  "maintain_protein": "include protein source in every dinner",
  "reduce_waste": "prioritize items expiring within 3 days",
  "schedule_fit": "busy days should have prep time under 25 minutes"
}
```

---

### 6. Meal Candidate Generator Harness

Generates multiple meal options per day.

Example Monday candidates:

- Spinach dal rice bowl
    
- Spinach paneer paratha
    
- Spinach chickpea curry
    

Then the optimizer chooses the best option.

---

### 7. Optimization + Scoring Harness

Scores meals based on:

- Waste reduction
    
- Health value
    
- Family preference fit
    
- Cooking/prep time
    
- Shopping minimization
    

Example scoring model:

```text
Waste reduction score: 30%
Health score: 25%
Family preference score: 20%
Cooking time score: 15%
Shopping minimization score: 10%
```

---

### 8. Safety + Health Policy Harness

Handles health-sensitive goals.

For POC, keep it basic:

- Do not claim medical advice.
    
- Respect allergies strictly.
    
- Treat diabetes/weight loss as dietary preferences unless medically verified.
    
- Escalate risky goals.
    

---

### 9. Approval Policy Harness

Decides what needs user approval.

No approval needed:

- Draft meal plan
    
- Read inventory
    
- Read calendar
    
- Suggest reminders
    

Approval needed:

- Add shopping list items
    
- Create reminders
    
- Create to-dos
    
- Order groceries
    
- Change existing plan
    
- Share information externally
    

---

### 10. Action Execution Harness

Executes only approved actions.

Possible actions:

```json
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

Returns execution status:

```json
{
  "shopping_list_update": "success",
  "reminder_creation": "success"
}
```

---

### 11. Event Monitoring Harness

Supports long-running goals.

Can monitor:

- Calendar changes
    
- Inventory changes
    
- Near-expiry alerts
    
- Missed prep reminders
    
- Shopping list status
    
- Plan conflicts
    

For the first POC, one monitoring scenario is enough:

- Calendar conflict / busy-day adaptation
    

---

### 12. Adaptation Harness

Decides whether the active goal needs adjustment.

Example:

```text
Wednesday football match found.
Dinner prep time is 45 minutes.
Recommended action: move prep to Tuesday evening.
Approval required: yes.
```

---

### 13. Explanation Harness

Creates user-friendly reasoning.

Every plan should explain:

- Why this meal?
    
- What inventory does it use?
    
- What health goal does it support?
    
- What does it avoid?
    
- What action is needed?
    

Example:

> I picked spinach dal on Monday because spinach expires soon, dal adds protein, and it avoids processed ingredients.

---

### 14. Failure Recovery Harness

Keeps the demo stable.

Examples:

- Inventory unavailable → use mock inventory
    
- Calendar unavailable → skip schedule optimization
    
- Recipe API fails → use cached recipes
    
- Shopping list update fails → show retry
    

---

### 15. Audit + Trace Harness

Tracks the full agent flow.

Example trace:

```text
Goal received
→ Ambiguity resolved
→ Device task created
→ Inventory read
→ Calendar checked
→ Plan optimized
→ Approval requested
→ Shopping list updated
→ Reminder created
→ Goal monitoring active
```

This can power a presenter/architect view.

---

## 11. Strongest IP Harnesses

The most important harnesses to showcase as IP:

1. Goal-to-Action Compiler
    
2. Capability-Aware Planner
    
3. Approval Policy Engine
    
4. Context Optimizer
    
5. Long-Running Adaptation Engine
    
6. Audit/Trace Harness
    

---

## 12. POC Success Metrics

The POC should demonstrate:

- Strong UX demo
    
- Architecture feasibility
    
- Cloud-device collaboration
    
- Agent orchestration
    
- Long-running task handling
    
- Human-in-the-loop approvals
    
- Device-side execution visibility
    
- Adaptive behavior after initial planning
    

---

## 13. Open Areas to Refine with Coding Agent

- Exact Family Hub runtime feasibility
    
- How Semantic Kernel will run on-device
    
- Cloud-to-device messaging protocol
    
- Device-to-cloud event format
    
- iPad UI framework
    
- Family Hub UI framework
    
- Mock API schemas
    
- Goal/task schema
    
- Approval event schema
    
- State machine implementation
    
- Presenter/architect mode
    
- Which harnesses to build first
    
- What should be mocked vs real for first demo
    
- How to simulate the mid-week adaptation event