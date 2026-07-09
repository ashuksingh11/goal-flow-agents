
## Request 
```json
{
  "goal_id": "meal-2026-w29",
  "objective": "healthier family dinners, less food waste",
  "scope": { "meal": "dinner", "days": ["Mon","Tue","Wed","Thu","Fri"] },
  "time_window": { "start": "2026-07-13", "end": "2026-07-17" },
  "constraints": {
    "hard": { "allergens": [], "dietary": ["no_pork"], "medical": [] },
    "soft": { "dislikes": ["mushrooms"], "prefer": ["more_vegetables","more_protein"] }
  },
  "optimization": ["reduce_processed", "reduce_waste"],
  "autonomy": "propose_all",
  "context_hints": { "notes": "son has sports Wednesday" },
  "reply_to": "kb/device/meal-2026-w29"
}
```


## Response
``` json
{
  "type": "plan_ready",
  "goal_id": "meal-2026-w29",
  "correlation_id": "disp-001",
  "task_status": "awaiting_approval",
  "payload": {
    "plan": [
      { "day": "Mon", "dish": "spinach rice bowl", "why": ["more_vegetables","uses_inventory"] },
      { "day": "Tue", "dish": "chickpea curry",    "why": ["plant_protein","no_mushrooms"] },
      { "day": "Wed", "dish": "grilled chicken + veg", "why": ["lean_protein"] }
    ],
    "proposals": [
      { "proposal_id": "p1", "action": "add_to_shopping_list",
        "items": ["bell peppers","lentils","yogurt"],
        "reason": "needed for Tue & Thu dishes", "requires_approval": true }
    ],
    "safety": { "gate": "passed", "hard_violations": [] }
  }
}
```

## Proposal
```json
{
  "type": "proposal",
  "goal_id": "meal-2026-w29",
  "correlation_id": "evt-014",
  "task_status": "adapting",
  "payload": {
    "proposal_id": "p7",
    "action": "add_prep_task",
    "detail": "marinate Wed's chicken on Tue night",
    "trigger": "calendar: son football Wed 18:00 — prep window shrinks",
    "requires_approval": true
  }
}
```

## Approval
```json
{
  "type": "approval",
  "goal_id": "meal-2026-w29",
  "correlation_id": "evt-014",
  "payload": { "decisions": [ { "proposal_id": "p7", "approved": true } ] }
}
```
