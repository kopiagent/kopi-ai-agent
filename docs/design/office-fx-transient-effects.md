# Office FX — transient one-shot effects for the pixel office

> Status: **design** (not yet implemented) · 2026-07-31
> Related: `web/src/pages/OfficePage.tsx` (renderer), `kopi_cli/web_server.py`
> (`/api/office/state`, `/api/events`, `_office_watcher`), `tools/delegate_tool.py`
> (`note_tool_activity`, `_write_office_snapshot`).

## 1. Problem & goal

The pixel office today is driven by a single **state-snapshot** stream
(`office.state`): the backend broadcasts the full list of live agents whenever a
displayed field changes, and the renderer derives all NPC motion (walk-in, walk
to workstation, walk-out, labels) by diffing snapshots. This is the right model
for *observing state* — it is idempotent, reconnect-safe, and self-healing (a
dropped frame or a late subscriber recovers from the next snapshot).

What it **cannot express** is a **transient one-shot action**: something that is
not a durable state and should play once and disappear — e.g.

- a discrete tool call (the ~100 ms ones the 600 ms snapshot poll coalesces away),
- a delegate hand-off (parent → child),
- an error (shake / red flash),
- a task-done celebration.

This spec adds a **second, transient stream** — `office.fx` — layered *on top of*
the state stream, so those effects can be implemented later by (a) calling one
backend helper at the relevant hook and (b) adding one `case` in the renderer.
The protocol does not change per effect.

## 2. Principles

- **State = snapshot (durable truth).** `office.state` is unchanged and remains
  the single source of truth for who exists / where they sit.
- **Action = transient FX (fire-and-forget).** `office.fx` carries one-shot
  effects. Losing one just drops a sparkle — it never desyncs the office, because
  the durable view still comes from the snapshot.
- **Small core + escape hatch.** A fixed handful of `kind`s plus a generic
  `emote`/`speak` so most future effects need no protocol change.
- **Lifecycle stays in state.** spawn / despawn / walk-to-station are still
  *derived* from `office.state`; they are deliberately **not** FX (no double
  source of truth).

## 3. Message schema — `office.fx`

Delivered on the existing `office` event channel (`/api/events?channel=office`),
same envelope as `office.state`; clients `switch` on `params.type`.

```jsonc
{
  "method": "event",
  "params": {
    "type": "office.fx",
    "payload": {
      "v": 1,                 // schema version — clients ignore/downgrade on mismatch
      "fx": [                 // batch; the watcher coalesces a poll window into one frame
        {
          "seq": 12841,       // monotonic per emitting process — client dedups (reconnect re-sends)
          "ts": 1785000000.1, // emit time (epoch seconds)
          "kind": "tool_call",
          "agent": "sub-abc", // subject NPC id ("main" = main session)
          "target": "sub-def",// optional — relational effects (hand-off parent→child)
          "data": { "tool": "grep_search" }  // kind-specific, optional
        }
      ]
    }
  }
}
```

**Contract rules**

- Unknown `kind` → renderer ignores it (forward-compatible).
- `v` mismatch → renderer ignores the frame (or applies a documented downgrade).
- `fx` may be empty; `target`/`data` are optional.
- Fire-and-forget: no ack, not persisted, not replayed. A late subscriber simply
  misses past effects; the snapshot re-syncs durable state.

## 4. Effect vocabulary (v1)

| `kind`       | subject / relation | `data`         | suggested animation                                   | backend trigger |
|--------------|--------------------|----------------|-------------------------------------------------------|-----------------|
| `tool_call`  | agent              | `{tool}`       | spark at the workstation + floating tool name (recovers fast calls the snapshot coalesces) | `note_tool_activity` |
| `handoff`    | agent → target     | —              | a ticket/paper flies from parent NPC to child         | `delegate_task` spawns a child |
| `error`      | agent              | `{message?}`   | red flash + shake + `!` bubble                        | tool exception / API 4xx–5xx |
| `retry`      | agent              | —              | hourglass / coffee sip                                | rate-limit / retry backoff |
| `done`       | agent              | `{ok}`         | ✓ pop + small hop                                     | turn ends successfully |
| `speak`      | agent              | `{text}`       | speech bubble                                         | any (optional) |
| `emote`      | agent              | `{emoji}`      | generic bubble — **escape hatch: no new kind needed** | any |

## 5. Transport (cross-process)

Agents run in a **different process** than the `web_server` that owns the WS
subscribers (PTY chat child, gateway, cron). Two options:

### A. Piggyback on the snapshot files — **recommended**

- Each agent record gains a bounded ring `fx: [{seq, ts, kind, target?, data?}]`
  (last ~8 entries, TTL ~5 s).
- `_write_office_snapshot()` includes it; hooks append to it.
- `_office_watcher`, when it reads the snapshot, broadcasts a separate
  `office.fx` frame for the **new** entries (by `seq`), alongside `office.state`.
- ✅ Reuses the entire existing pipeline; works uniformly for **CLI / gateway /
  cron / PTY** agents. Latency = watcher poll (~600 ms), with coalescing.

### B. Direct low-latency publish — optional add-on

- PTY-child agents already hold an `/api/pub` publisher (`_build_sidecar_url`);
  they can publish `office.fx` directly for <50 ms latency. Non-PTY agents fall
  back to (A).
- More moving parts — add only if a `tool_call` spark needs to feel instant.

**Recommendation:** ship (A) first (zero new transport, full coverage); add (B)
later if needed.

## 6. Backend emit API

In `tools/delegate_tool.py`, alongside `note_tool_activity`:

```python
def office_fx(agent, kind, *, target=None, data=None):
    """Append a transient effect for `agent` (fire-and-forget).

    Matches the same agent record note_tool_activity resolves (main session or a
    specific subagent), pushes one entry onto that record's bounded `fx` ring
    (monotonic `seq`), then best-effort `_write_office_snapshot()`. Never raises.
    """
```

Suggested hook points:

- `note_tool_activity(...)` → also `office_fx(agent, "tool_call", data={"tool": tool_name})`
- `_run_single_child(...)` (delegate spawn) → `office_fx(parent, "handoff", target=child_id)`
- `tool_executor` exception / error classifier 4xx–5xx → `office_fx(agent, "error", data={"message": ...})`
- `mark_main_turn_end(...)` on success → `office_fx("main", "done", data={"ok": True})`

## 7. Frontend handling (`OfficePage.tsx`)

- Subscription unchanged. In the WS `message` handler, branch on `params.type`:
  - `office.state` → `applyAgents(...)` (unchanged)
  - `office.fx` → `playFx(payload.fx)`
- `playFx(list)`: dedup by `(agent, seq)` (reconnect re-sends are harmless); attach
  a transient `effects: [{ kind, startAt, data }]` entry to the matching `Npc`.
- The render loop draws active effects on top of the NPC and expires them after a
  short duration (e.g. 800 ms). A missing FX = a missing sparkle, never a desync.

## 8. Robustness summary

- Fire-and-forget, loss-tolerant, order-independent; durable state always comes
  from the snapshot.
- `seq`-based client dedup survives reconnect re-delivery.
- Bounded `fx` ring + TTL caps payload; unknown `kind` ignored (forward-compat);
  `v` gates schema evolution.
- Clear separation of concerns: `office.state` = persistent state, `office.fx` =
  one-shot action.

## 9. Adding a new effect later (the whole cost)

1. Backend: call `office_fx(agent, "<kind>", data=...)` at the relevant hook.
2. Frontend: add one `case "<kind>"` in the effect renderer.

No protocol/schema change for anything the `emote`/`speak` escape hatch can carry.

## 10. Open questions / deferred

- Latency: is ~600 ms (option A) good enough for `tool_call` sparks, or do we
  want option B for PTY chats?
- Dedup window size for `seq` on the client (LRU size vs memory).
- Whether `speak`/`emote` should be rate-limited server-side to avoid bubble spam.
- Desktop app: same `office` channel is reachable (backend is `kopi serve`), so
  this design applies unchanged once the office page is ported to desktop.
