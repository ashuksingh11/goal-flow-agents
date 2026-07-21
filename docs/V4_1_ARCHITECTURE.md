# v4.1 Architecture — surface-aware delivery + the chat-webview lifecycle

Design note for the v4.1 contract change (spec'd in
`goal-flow-cloud-agent/CONTRACT.md`, now v4.1 — that file is canonical; this note is
the rationale + the code-phase map). Plan: `docs/V4_PLAN.md` §v4.1.

## 1. What changes on the wire

Four additive things, one version bump:

1. `hello.surface` — optional, ui-only: `"input" | "chat" | "board"`. Absent ⇒ full
   broadcast (every v3 client is an absent-surface client, so nothing breaks).
2. A delivery **fork for `"input"` only**, applied at the cloud's single fan-out point.
3. `chat_ui_open { goal_id }` / `chat_ui_close { goal_id }` (cloud → ui) — the
   create-phase bracket. Bixby opens/closes the webview on them; the chat UI treats
   open as a hard reset keyed to the new `goal_id`.
4. A per-session **create-phase replay cache** the cloud replays to a freshly-bound
   `"chat"` socket.

## 2. Why

On the Family Hub, Bixby is a **native app**, not a web page. It sends `user_goal` and
otherwise wants five frames — everything else in the session broadcast
(`agent_event`, `status`, board frames…) it would parse and drop. The chat UI becomes
an **ephemeral webview** that exists only during the create phase; its two standing
bugs — the previous goal's UI repainting when Bixby reuses the webview, and the race
between the webview connecting and `understanding` being computed — are both
lifecycle bugs, so they get lifecycle fixes (reset-on-open + replay-on-bind), not
routing fixes. `chat`/`board` deliberately stay on broadcast: their split is
*temporal, not type-based*, their client `INBOUND_TYPES` allowlists already filter,
and a server-side per-type table for them would reintroduce the "forked to nobody =
silently dropped" failure mode CONTRACT.md opens by warning about.

## 3. Delivery table (the fork)

Consulted per target socket inside `ConnectionRegistry.send_to_uis`'s send loop
(`goal-flow-cloud-agent/src/goalflow_cloud/server.py:312-324` — the ONE fan-out
point) and for the bind-time pushes in `_bind_ui` (`server.py:221-245`). Recommended
form: a pure predicate `wants(surface, frame_type) -> bool`, so no call site changes.

| surface | receives via session fan-out |
|---|---|
| absent / `""` (all v3 clients) | everything (unchanged) |
| `"chat"` | everything (unchanged; client allowlist filters) + create-phase replay on bind |
| `"board"` | everything (unchanged; client allowlist filters) |
| `"input"` | ONLY `hello_ack`, `goal_accepted`, `chat_ui_open`, `chat_ui_close`, `notice` |

Point-to-point handshake/discovery sends (`hello_ack` via `_ack`, `devices` via
`send_devices`/`broadcast_devices`, `server.py:264-267, 359-384`) are outside the
fork — an input surface still needs the device picker to bind.

**Where `surface` lives server-side:** `Session.uis` is a flat `list[WebSocket]`
(`server.py:134-146`), so surface is per-socket state, not session state — it extends
the registry's reverse-lookup `_meta: ws -> (role, device_id)` (`server.py:164`) to
`(role, device_id, surface)`, captured from `Hello` at the handshake
(`server.py:414-421` → `register_ui` `server.py:197`), immutable for the socket's
lifetime, and it survives rebinds because `_bind_ui` rewrites `_meta` anyway
(`server.py:230`).

## 4. The create-phase bracket

**`chat_ui_open { goal_id }`** fires in `handle_user_goal` at the first moment the
cloud knows the goal will have a create phase: after `start_goal` returns, on every
path that did NOT take the error return (`server.py:698-708`) or the out-of-scope
`notice` return (`server.py:713-722`) — i.e. immediately before the `understanding`
broadcast (`server.py:739`) and before the direct-dispatch fallback
(`server.py:747-754`). Ordering guarantee: **open precedes `understanding`** on the
wire. Accepted suggestions funnel through `handle_user_goal`
(`server.py:574-577`), so they bracket identically. Out-of-scope ⇒ `notice`, no open,
no webview — Bixby just speaks it.

Dual role: `input` opens (or ensures open) the webview; `chat` HARD-RESETS keyed to
`goal_id` and thereafter ignores goal-scoped frames with a different `goal_id`. The
reset is idempotent per goal — re-receiving open for the already-keyed goal is a
no-op, or the bind-time replay would wipe the state it is about to restore.

**`chat_ui_close { goal_id }` — trigger decision: on the initial `approval` frame**
(`handle_approval`, `server.py:844-853`), NOT after the device confirms execution
started. Rationale:

- *Snappiness is the point*: the webview should vanish at the user's final tap.
- *There is nothing reliable to wait for*: post-approval the device may stream
  `phase:"executing"`, or defer everything (`deferred_precheck`), or be offline —
  `send_to_device` returning `False` already yields a terminal status
  (`server.py:621-639`). Close-on-approval is correct in all of those futures;
  close-on-execution leaves a dead webview open precisely when things go wrong.
- The v3.1 handoff already *defines* approval as the moment the board becomes the
  primary surface; this frame makes that handoff physical.

**Declined/aborted create flows also close** — yes, emit it:

| trigger | where |
|---|---|
| initial `approval` for the create-phase goal | `handle_approval` (`server.py:844-853`) |
| `understanding_response { confirmed: false }` | declined branch (`server.py:784-806`) |
| terminal error status after open (e.g. contract-not-built) | `server.py:808-835` |

Guard: emit only while the goal is still the session's **current create-phase goal**
(the replay-cache key) — that is what stops adaptation-time `approval` frames from the
board retriggering a close. Pairing invariant: close(g) only after open(g); a
superseding open for a NEW goal replaces the phase **without** an intervening close
(Bixby's rule — close only on matching `goal_id`; open = ensure-open-and-retarget —
turns the supersede into a retarget instead of a close/reopen flicker).

## 5. Create-phase replay cache

Per session: `{ goal_id, understanding?, present_plan? }` — the exact frames as
broadcast (`present_plan` *including* `payload.knew`). Natural home: a field on
`Session` (`server.py:134-146`), since its lifetime is session-scoped and
`_bind_ui` already holds the `Session` when it replays.

- **created** at `chat_ui_open` emission; `understanding` captured where it is sent
  (`server.py:728-739`); `present_plan` captured in `handle_plan_ready`
  (`server.py:912-918`) when the goal is the create-phase goal.
- **cleared** at `chat_ui_close` (any trigger). Lifetime is exactly the bracket:
  "until close", where a superseding open counts as an implicit close-and-replace —
  this also answers "until next goal?" (same thing, by construction).
- **replayed** in `_bind_ui` after the existing capability/board pushes
  (`server.py:236-245`), to sockets whose surface is `"chat"` ONLY (a legacy
  absent-surface client keeps byte-for-byte v3 behaviour): `chat_ui_open`, then
  cached `understanding` (only while no plan yet), then cached `present_plan`. Board
  keeps its own rehydrate (`_replay_board` `server.py:326-343`, `goal_state_get`
  `server.py:581-618`); this mirrors it for the webview.

The board already caches these payloads for `goal_state_get`
(`board.py:78-86` — `cached_plan`/`cached_status`/`cached_understanding`), but those
are keyed by goal and shaped for drill-in; the create-phase cache is keyed by
*session* and answers a different question — "which goal is the webview about, right
now" — so it is a separate, tiny structure rather than an overload of the board fold.

## 6. Walkthroughs

### (i) First goal

```
Bixby(input)                 cloud                        chat webview        board
user_goal ─────────────────▶
            ◀─ goal_accepted (in input allowlist)                     ──▶ (board too)
                 gate passes
            ◀─ chat_ui_open {g1}          [cache: {g1}]
  opens webview ──────────────────────▶ connect, hello{surface:"chat"}
                                        ◀─ hello_ack
                                        ◀─ replay: chat_ui_open{g1} (reset→g1)
                             understanding ──▶ (broadcast; input NOT delivered)
                                        ◀─ understanding   [cache: +understanding]
                                        understanding_response{confirmed} ─▶
                             dispatch ─▶ device … plan_ready
                                        ◀─ present_plan    [cache: +present_plan]
                                        approval ─▶
            ◀─ chat_ui_close {g1}         [cache cleared]
  closes webview                                                     board owns g1
```

If the webview finishes connecting BEFORE `understanding` exists, the replay delivers
only `chat_ui_open{g1}` and the `understanding` arrives by ordinary broadcast moments
later; if it connects AFTER, the replay delivers open + understanding (or open +
present_plan). **Both orders paint the same screen — the race is gone.**

### (ii) Second goal, same session (the stale-UI bug)

Bixby reuses (hides/shows) the same webview; its React state still holds g1's
approved plan, and its socket may still be open.

```
user_goal (g2) ────────────▶
            ◀─ goal_accepted
            ◀─ chat_ui_open {g2}          [cache: {g2} replaces any leftovers]
  shows webview ──────────────────────▶ (socket still open)
                                        ◀─ chat_ui_open{g2}: HARD RESET → fresh
                                           "listening" stage keyed g2; every g1
                                           frame now ignored by goal_id filter
                             understanding(g2) ──▶
                                        ◀─ understanding(g2) … (as in (i))
```

If Bixby instead RELOADED the webview, the fresh socket binds with
`surface:"chat"` and the replay repaints g2's current state. Reset covers the
reused-webview path, replay covers the reloaded-webview path — applying both is what
makes the fix robust regardless of which Bixby does.

## 7. bixby-ui component shape (dev surrogate)

Repo `goal-flow-agent-bixby-ui` (skeleton exists: AGENTS.md + README). A deliberately
tiny Vite/TS app — it is a stand-in for native code the user ports by hand, so no
framework weight:

- `src/lib/ws.ts` — the module-level-singleton socket pattern copied from board-ui
  (`goal-flow-agent-board-ui/src/lib/ws.ts:1-49`), `hello{role:"ui",
  surface:"input"}`, `INBOUND_TYPES = {hello_ack, devices, goal_accepted,
  chat_ui_open, chat_ui_close, notice}`.
- `src/types/contract.ts` — mirror (only the frames above + `user_goal`,
  `select_device`).
- `App` — a text box + Send (the ASR stand-in), a device picker (reuses the
  `devices`/`select_device` flow), a notice banner ("Bixby speaks this"), and a
  webview surrogate: an `<iframe>` pointing at the chat UI, mounted on
  `chat_ui_open` / unmounted on `chat_ui_close{matching goal_id}` — mount/unmount
  (not hide/show) so the dev surrogate exercises the RELOAD path while the chat UI's
  reset handles the reuse path a real Bixby may take.

## 8. Code-phase touchpoints & mirror checklist (one pass, no partial merges)

**Gate:** `goal-flow-cloud-agent/scripts/verify_mirrors.py` is RED as of the spec
commit — its 12 findings are this checklist in executable form. Green = mirrors done.

`goal-flow-cloud-agent`:
- `src/goalflow_cloud/models/contract.py` — `Hello` (+`surface`, `:80-94`); new
  `ChatUiOpen`/`ChatUiClose` models (beside `Notice`, `:472`); add to the message
  union (`:677`).
- `src/goalflow_cloud/server.py` — `_meta` 3-tuple (`:164`); `register_ui`/
  `_bind_ui` accept + store surface, chat replay hook (`:197-245`); interest
  predicate in `send_to_uis` (`:312-324`) and `_bind_ui` pushes; `Session.
  create_phase` field (`:134-146`); emit open in `handle_user_goal` (`:724-745`,
  before `:739`); capture plan in `handle_plan_ready` (`:912-918`); emit close in
  `handle_approval` (`:844-853`), declined-understanding (`:784-806`), and the
  post-open terminal-error path (`:808-835`); pass `hello.surface` at `:421`.
- `scripts/verify_mirrors.py` — add `chat_ui_open`/`chat_ui_close` to
  `DEVICE_EXEMPT` (`:37` — the device never sees them) and to the UI outbound
  exemptions as needed (`:49-95`).

`goal-flow-agent-chat-ui`:
- `src/types/contract.ts` — `ChatUiOpen`/`ChatUiClose`; `hello.surface`; extend
  `UiInboundMessage` (`:556`).
- `src/lib/ws.ts` — `INBOUND_TYPES` +2 (`:33`); send `surface:"chat"` in hello.
- `src/App.tsx` — DELETE `GoalComposer` (`:956-992`) and its render (`:876`);
  `reduceInbound` (`:332-548`): `chat_ui_open` ⇒ hard reset keyed to `goal_id`
  (reuse the `notice` reset shape `:385-413`, idempotent per goal) + strict
  goal_id filter; `chat_ui_close` ⇒ idle/handoff state (the `:938-947` banner
  becomes the pre-close beat).

`goal-flow-agent-board-ui`:
- `src/types/contract.ts` — the two new types (`UiInboundMessage :521`).
- `src/lib/ws.ts` — `INBOUND_TYPES` +2 as DELIBERATELY IGNORED (`:36-49` — the
  board stays on broadcast, so unlisted = console-warn spam); send
  `surface:"board"` in hello.

`goal-flow-agent-bixby-ui` — new app per §7.

Device repos (`goal-flow-device-agent-ubuntu` `Contracts/*.cs`, tizen, tizen-ui) —
**untouched**: `surface` is ui-only and the device neither sends nor receives the new
frames (hence `DEVICE_EXEMPT`).

## 9. Open questions surfaced by this design (for the code phase / v4.2)

**Resolved by the user (2026-07-21):**
- **Q1 superseded create-phase goal** → *acceptable for v4.1*. No auto-abort; a goal
  superseded mid-create lingers at its gate, reachable via the board's drill-in.
- **Q3 `notice.kind:"declined"`** → *ADD it in v4.1*. On a declined understanding gate
  (and on an aborted create flow), the cloud emits BOTH `chat_ui_close {goal_id}` AND a
  `notice { kind:"declined", message }` so the input (Bixby) surface can speak the
  cancellation. `notice.kind` is now `"out_of_scope" | "declined"` (no longer reserved).
- Q2 (input-surface `suggestions`) remains deferred to v4.2.

Original list:


1. **Multiple concurrent create phases.** The cache holds ONE create-phase goal per
   session; a second `user_goal` before the first close supersedes it. Fine for the
   one-webview Bixby flow, but a goal superseded mid-create is still alive at its
   understanding gate — reachable only via the board's drill-in (`goal_state_get`).
   Acceptable? (The board card + `waiting` chip already cover it; flagging, not
   blocking.)
2. **Input-surface `suggestions`.** Should Bixby ever *speak* proactive suggestions?
   Today `suggestions` is not in the input allowlist (board surface). If v4.2 wants
   voice suggestions, that is one allowlist row — no protocol change.
3. **`notice.kind:"declined"`** is still reserved; the declined-understanding close
   path sends a terminal `status`, not a `notice`. If Bixby should *speak* a
   cancellation confirmation, the code phase may want to promote it. Not required for
   the bracket to work.

## 10. Fixes after the live smoke (2026-07-21)

The build-clean + WS-smoke pass used a one-proposal goal, so it missed the first two of
these. All found by driving the real browser stack end-to-end; all verified live.

1. **Multi-proposal approval must be batched (chat-ui `6b39ea8`).** The chat-ui sent one
   `approval` frame per proposal click; the device resumes the whole plan on the FIRST
   frame (its `decisions[]` is the complete set — now stated in CONTRACT.md's `approval`
   section), so later proposals (a firm grocery order) were silently dropped and the
   webview closed after the first click. `sendDecisions` now records each click locally
   and emits ONE `approval` with every decision once all approval-required proposals are
   decided. No cloud/device change — `chat_ui_close`-on-approval is correct once the frame
   is complete.
2. **Offline-device self-heal (chat-ui `8752f5f`, board-ui `ade4869`, bixby-ui `8e0dafc`).**
   The cloud's `devices` list is online-only (offline devices omitted), and the UIs treated
   a truthy `hello_ack.device_id` as permanently bound — so a stale `?device=`/`localStorage`
   pairing bound to an empty session and declined every goal with `no_capabilities`
   ("can't see a device"), never showing the picker. Each UI now treats "bound id absent
   from the live `devices` list" as offline and self-heals: auto-rebind (`select_device`)
   to the sole online device, else show the picker. (CONTRACT.md `devices` section documents
   the online-only + self-heal contract.) No cloud change — kept the list online-only to
   avoid ghost devices cluttering pickers.
3. **Planning-progress UX (chat-ui `8752f5f`, device `305eee5`).** Plan compose is a
   NON-streaming ~60-90s LLM call — zero frames — so the create stage looked frozen, and
   the device separately dumped the raw plan JSON onto the `thinking` channel. Device: removed
   the two `_trace.ThinkingAsync(raw)` emits (kept `AddAssistantMessage`; grounding's genuine
   streamed prose thinking untouched). chat-ui: renders the prose thinking live, suppresses
   JSON-shaped thinking, and shows a rotating text-only indicator ("Composing your plan…" ↔
   "Checking budget & constraints…" + elapsed counter) during `phase:"planning"`. No contract
   change.
