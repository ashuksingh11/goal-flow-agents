# GoalFlow v4 — Plan

Trunk baseline: `master` (== v3, through v3.6.2). Every repo now carries a `v4` branch
(chat-ui's stale `master` was fast-forwarded to `v3` first). v4 work happens on `v4`
branches; milestones merge back per the usual convention.

---

## v4.1 — Bixby entry point + surface-aware delivery

### Motivation (the real Tizen flow)

On a Family Hub, **Bixby is a native app**, not a web page. The production loop is:

1. Tap Bixby → native input → speak → on-device **ASR** → text.
2. Bixby sends the text to the cloud as `user_goal` (declaring `surface: "input"`).
3. Cloud interprets. If actionable → cloud sends **`chat_ui_open`** → Bixby opens a
   **webview** hosting the chat UI; the create/planning phase renders there (mirrored on
   the board). If out-of-scope → cloud sends `notice`; Bixby speaks it, **no webview**.
4. Initial plan approved → cloud sends **`chat_ui_close`** → Bixby closes the webview;
   execution continues on the **Agent Board**.
5. A new utterance repeats the cycle.

So the chat-UI webview is **ephemeral** — it exists only between `chat_ui_open` and
`chat_ui_close` (i.e. only during the create phase).

### Decisions

**1. New repo `goal-flow-agent-bixby-ui`** — a browser **dev surrogate** for native
Bixby. Sends `user_goal` (`surface:"input"`; a text box replaces ASR in dev) and
opens/closes the chat UI on `chat_ui_open`/`chat_ui_close`. Renders no plan/board content.
The user ports this behaviour into the native Bixby app by hand.

**2. Remove the chat UI's input box entirely.** Goal text now originates from the Bixby
surface. The chat UI becomes render-only for the create phase (understanding → plan →
tiered approval) plus its two approval controls (`understanding_response`, `approval`).

**3. Surface-aware delivery — fork the `input` surface only.**
- Add an **optional** `surface` field to `hello` for UIs: `"input" | "chat" | "board"`.
  **Absent ⇒ receives everything** (backward-compatible with all v3 clients).
- At the single fan-out point (`ConnectionRegistry.send_to_uis`, cloud
  `server.py`), the **`input` surface receives only lifecycle/ack frames**:
  `hello_ack`, `goal_accepted`, `chat_ui_open`, `chat_ui_close`, `notice`. Never the
  `agent_event`/`status`/board firehose it would discard.
- **`chat` and `board` stay on broadcast** + their existing client-side `INBOUND_TYPES`
  allowlists. Their split is *temporal, not type-based*, and the ephemeral webview
  lifecycle already scopes the chat UI in time — so no phase-aware server routing is
  needed. (Full type-forking for chat/board is a possible later refinement, not v4.1.)

Rationale: your desired flow already works under pure broadcast (all UIs share the
`device_id` session, so a separate Bixby *sender* and a separate chat *renderer* compose
for free). Forking is therefore an **optimization**, valuable precisely where a
resource-constrained *native* client (Bixby) should not be fed frames it drops. Doing it
only for `input` avoids a brittle per-type routing table and the "forked to nobody =
silently dropped" failure mode the CONTRACT already warns about.

**4. New lifecycle frames (cloud → ui):**
- `chat_ui_open { goal_id }` — emitted after the actionability gate passes, before/with
  `understanding`. Bixby opens the webview; the chat UI treats it as a **hard reset**
  signal (see §5).
- `chat_ui_close { goal_id }` — emitted when the initial plan is approved. Bixby closes
  the webview; the board owns everything after.

**5. Fix "old UI shown on the next goal."** Root cause: Bixby reuses (hides/shows) the
same webview instance, so the chat UI's prior-goal React state repaints. Two fixes, both
applied so it is robust regardless of whether Bixby reuses or reloads the webview:
- **`chat_ui_open` = reset.** The chat UI hard-resets to a fresh "listening…" state keyed
  to the new `goal_id` and ignores frames for any other goal.
- **Cloud caches + replays create-phase state to a freshly-bound `chat` surface**
  (mirrors how the board rehydrates via `present_plan` / `board_snapshot`). Removes the
  race between the webview connecting and `understanding` being computed — on bind, the
  chat surface pulls the current goal's understanding/plan.

### Contract surface (v4.1 additions — all additive)

| addition | direction | why |
|---|---|---|
| `hello.surface: "input"\|"chat"\|"board"` (optional) | ui → cloud | lets the hub fork the input surface; absent ⇒ everything |
| `chat_ui_open { goal_id }` | cloud → ui | Bixby opens webview; chat UI resets to this goal |
| `chat_ui_close { goal_id }` | cloud → ui | Bixby closes webview; board takes over |
| create-phase replay to a bound `chat` surface | cloud internal | rehydrate the webview on (re)open; kills the connect/understanding race |

All mirrors move in one pass (CONTRACT.md is canonical): `contract.py`, chat-ui &
board-ui & bixby-ui `contract.ts`, device `Contracts/*.cs`. Contract version bump.

### Repos touched in v4.1

- `goal-flow-cloud-agent` — `surface` field, input-surface fork in `send_to_uis`,
  `chat_ui_open`/`chat_ui_close` emission, create-phase replay cache. **CONTRACT.md** bump.
- `goal-flow-agent-chat-ui` — remove input box (`GoalComposer`), reset-on-`chat_ui_open`,
  bind with `surface:"chat"`.
- `goal-flow-agent-bixby-ui` — **new**; the dev surrogate.
- `goal-flow-agent-board-ui` — bind with `surface:"board"` (no behaviour change; it
  already ignores create-phase frames).
- Device repos / tizen-ui — untouched in v4.1 (v4 branch created for consistency).

### Open questions

- Exact `chat_ui_close` trigger: on the `approval` frame, or only once the device confirms
  execution has actually started? (Leaning: on approval, for snappiness.)
- Whether to also push `chat_ui_close` on a declined/aborted create flow.

### Phases & models (v4.1)

- **Plan** (Opus) — this doc. ✅
- **Architecture** (Fable) — formalize the contract change (surface field, lifecycle
  frames, replay cache, fork semantics) into CONTRACT.md + a design note; define the
  bixby-ui component shape. Durable artifact before any code.
- **Code** (Opus) — implement cloud fork + frames, chat-UI input removal + reset, build
  the bixby-ui app. Browsing/verification via Sonnet.

Confirm before each phase transition; each phase writes durable artifacts.
