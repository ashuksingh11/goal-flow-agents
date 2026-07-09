
The seven teal additions, ordered by the phase they serve, and why each earns a place in the demo:

- **Grounding / world-state assembler** (sense) — your adapters make raw calls; grounding normalizes them into one stable "current state" object (inventory + calendar + prior plan) that the planner reasons over. Without it the LLM is reasoning across three inconsistent API shapes. The IP line: the agent has a coherent model of the home, not a pile of responses.
- **Planner** (decide) — name the goal→plan reasoner as its own harness, because it's the swappable brain: LLM now, a constraint solver later, without touching anything else. Keep it strictly separate from the safety gate — the planner is fallible and probabilistic, the gate is code and absolute. Never let SK's planner run the safety check; that single merge would quietly destroy your guarantee.
- **Approval broker** (gate) — packages side-effects as approval requests, freezes them, tracks pending/approved/rejected/expired, and correlates the user's later "yes" back to the frozen action. Worth its own component because human-in-the-loop is the pattern's marquee feature.
- **Effect executor, idempotent** (act) — performs approved effects and guarantees a retried "add bell peppers" doesn't add them twice, recording what was done. Idempotency is exactly the "we handled the hard part" detail an architect audience looks for.
- **Scheduler / temporal engine** (sustain) — fires time-based actions off the virtual clock; this is the component that makes the operation _long-running_ at all, and it's where your demo's fast-forward plugs in.
- **Change / materiality watcher** (sustain) — notices the world moved, decides whether it's big enough to re-plan, and re-invokes the loop. This is your second headline: "adapts to reality" is a claim, and this is the engine behind it. For the POC its materiality rule can be one line (new calendar event overlapping a prep window → material), framed as a policy so it's visibly extensible.
- **Trace / audit log** (cross-cutting) — a structured record of every decision, tool call, gate outcome, and state change. Low effort, high narrative value: it's your explainability story for management ("here's exactly what it did and why"), your debugging tool, and it doubles as the demo's live activity feed.


**Harness summary — the full set (5 existing + 7 new):**

- **Task manager** _(orchestrate)_ — creates the task, assigns the goal ID, drives the status lifecycle. _existing_
- **Pre-check engine** _(sense)_ — validates access and permissions to inventory, calendar, meal planner, shopping list. _existing_
- **Capability manager** _(sense)_ — discovers which features/APIs are actually available locally and from cloud services. _existing_
- **Product API adapters** _(sense)_ — typed clients that call the underlying recipe, inventory, and calendar APIs. _existing_
- **Grounding / world-state assembler** _(sense)_ — normalises retrieved data into one coherent current-state object for the planner. _new_
- **Planner** _(decide)_ — turns contract + world-state + constraints into a candidate plan; LLM-backed, swappable. _new_
- **Safety gate** _(decide)_ — deterministic code check of the plan against the hard-constraint block; blocks on violation. _existing_
- **Approval broker** _(gate)_ — freezes side-effects as proposals, tracks pending/approved/rejected/expired, correlates the user's decision back. _new_
- **Effect executor** _(act)_ — performs approved effects against actuators, idempotently, with effect records. _new_
- **Scheduler / temporal engine** _(sustain)_ — fires time-based actions off the virtual clock. _new_
- **Change / materiality watcher** _(sustain)_ — detects world changes, applies a materiality policy, re-invokes the loop. _new_
- **Trace / audit log** _(cross-cutting)_ — structured record of every decision, tool call, gate outcome, and state transition. _new_