# Design: static-queryset-lists

## Context

ADR-0019 fixes the list interface (a bare queryset assigned to a
`many=True` field, membership derived client-side, rebind authoritative)
and ADR-0018 defines the tier this change builds: omitted routing = static
list — snapshot plus updates/deletes to known rows, no new-row delivery.
Today `rx.model(TaskSerializer(many=True))` crashes at class creation
(`StateModel._disassemble_nested` receives a `ListSerializer`, which has
no `.fields`), and the client (`StateBuilder`) assumes a single anchor per
model field.

Everything below the anchor is already solved and reused wholesale: flat
`_type`-tagged merge layers, `_v` watermarks, `_del` tombstones, the
layered walk with supersede (ADR-0012/0013/0014/0016).

## Goals / Non-Goals

**Goals:**

- `many=True` declarations compile; queryset assignment snapshots through
  the existing walk.
- Bind-time introspection with loud, named failures.
- The bind descriptor on the wire; client-derived membership with ordering;
  `null` / `[]` / `T[]` semantics; rebind-authoritative reset.
- Persistent socket with backoff; reconnect = rebind over a warm index.
- Generated `T[] | null` types; example app(s) with Playwright e2e.

**Non-Goals:**

- Routers and live new-row delivery (ADR-0018 proper — next change), and
  with them the Router-coverage arm of bind validation.
- Index eviction, pagination, delta reconnect, cascade-delete emission —
  all recorded as future work in ADR-0019.

## Decisions

### D1: The descriptor rides the snapshot anchor frame (`q` slot)

The anchor layer of a queryset walk is already a single frame carrying the
full anchor row set (one frame per layer). Attaching the descriptor to it
as a `q` key — instead of a separate descriptor frame — makes the basis
reset atomic: descriptor, snapshot membership, and anchor data arrive
together, so there is no demote-then-refill flash and no "which frame ends
the snapshot?" question. The empty case falls out (`v: []` + `q` → state
`[]`). `q` doubles as the "this is an authoritative snapshot" marker that
rebind and reconnect rely on. Alternative considered: a separate
`{"t": "desc"}` frame — rejected because it forces the client to hold a
pending-descriptor state and pick which later frame completes the
snapshot.

Spelling under ADR-0002's short-key rule: `q: {"w": [[column, lookup,
value], ...], "s": ["-created_at", ...]}`.

### D2: Membership basis = anchor pks of the last snapshot

Client model per list field: a *basis* (pk set) + the shared instance
index. Derived state = basis rows passing `w`, sorted by `s`. The basis
changes in exactly three ways: reset by a `q` frame, shrunk by `_del`
(existing detach path), never grown otherwise — new rows cannot join a
static list between snapshots, which is precisely the static tier's
contract. Rows failing `w` stay in the basis and the index; an update
frame flipping a residual column toggles derived membership with no extra
machinery. Demotion at reset keeps `_v` watermarks so stale frames cannot
resurrect old state.

Derivation runs on: `q` frame, any merge frame touching a basis row,
`_del` on a basis row. Each run that changes membership or order produces
a new array identity (reference-stability preserved for unchanged
elements, per the existing rebuild cache).

### D3: Introspection scope — conjunction of simple, serializer-local conditions

Walk `queryset.query.where` at bind. Supported: AND-trees of simple
lookups on anchor-serializer output fields, lookups `exact`, `in`, `gt`,
`gte`, `lt`, `lte`, `isnull`; ordering columns must be serializer fields.
Rejected loudly, naming the condition: OR/NOT nodes, joined (`__`)
column paths, unsupported lookups, non-JSON-serializable values,
non-serialized columns. This is deliberately the narrow v1 of ADR-0019's
"frame-evaluable" arm; the Router-coverage arm arrives with the routed
tier and only widens what passes.

Datetime values serialize to ISO-8601 UTC strings exactly as DRF renders
the field, so client comparison is string comparison over a uniform
format — the lookup-parity contract is tested per lookup on both sides
(Python emission tests, vitest evaluation tests, one e2e boundary case).

### D4: Server keeps zero membership state; groups follow the snapshot

The consumer joins per-instance groups for delivered rows exactly as
today (join-before-send relay, ADR-0016). On rebind/reassignment the
superseded walk's semantics extend naturally: the new walk's rows are
joined; rows only in the old snapshot are left, so a demoted row stops
producing frames. No member sets, no `anchor_index` — reconnect can land
on any worker.

### D5: `PersistentWebsocket` ported, reconnect = replay of `on_connect`

Port v0's `PersistentWebsocket` (exponential backoff, reset on open,
stop on last unsubscribe) as the transport under `ContextChannel`. No
server-side session resume: a reconnect is a fresh connection whose
`on_connect` re-runs and re-snapshots; the client keeps its index and
watermarks, and D1's `q` frames make the new snapshots authoritative.
Scalar fields simply take the new connection's pushes. This is
rebind-authoritative as the *only* healing mechanism — delta reconnect is
explicitly future work.

### D6: Codegen and metadata

`ListSerializer` unwrapping happens once in `StateModel` (fixing the
class-creation crash); the field records `many: true` into `_modelFields`
so the runtime routes it through D2 instead of the single-anchor path.
Generated property: `tasks: Task[] | null = null`. Elements are plain `T`
(never `Unloaded`) because snapshot anchors always arrive with full
layers; nested relations keep their stub unions.

### D7: Examples and e2e

One example app for the static list tier (docs-generated page +
hand-written demo, per the docgen pipeline), exercising: snapshot render,
live update to a member row, residual flip out/in, delete, ordering
change, and empty-vs-loading. Reconnect behavior gets an integration/e2e
test (kill the socket server-side, assert convergence after backoff).
The user's static-queryset example branch is the seed for this app.

## Risks / Trade-offs

- [Lookup parity drift — client verdicts diverging from Django's] →
  narrow supported set, uniform ISO-8601 UTC serialization, per-lookup
  tests on both sides of the boundary.
- [Basis-reset bugs make stale members immortal or lose live ones] →
  the reset is one small pure function over (basis, index, `q` frame);
  unit-test it directly, including the stale-frame-after-demotion case.
- [Group leave on supersede missed → demoted rows keep streaming] →
  integration test asserting no frames for dropped-from-snapshot rows
  after rebind.
- [`on_connect` re-run on reconnect has app-visible side effects] →
  documented semantics: `on_connect` must be idempotent per connection;
  already true of the existing examples.
- [Cascade deletes emit no tombstone (ADR-0013 boundary)] → known parked
  hole; rebind heals it; not widened by this change.

## Open Questions

None blocking. The exact backoff schedule (base/cap/jitter) is an
implementation constant; v0's values are the default.
