# 0019. Derive list membership client-side from a bare queryset interface

- **Date:** 2026-07-15
- **Status:** Active
- **Deciders:** Luis Fagundes

## Context

`rx.model(Serializer(many=True))` already works server-side — the layered
walk (ADR-0016) handles queryset anchors — but there is no list story: the
client `StateBuilder` latches onto a single anchor instance, `state` is
`T | null` rather than `T[]`, and an empty list is indistinguishable from a
not-yet-loaded one.

Forces:

- **The interface is the most important asset**, and it is the governing
  constraint this architecture was derived from: the developer assigns a
  plain Django queryset and writes nothing else. No declaration language,
  no new verbs. An earlier design that compromised this (declared query
  shapes, `bind()`) was rejected during review along with the
  server-authoritative membership it implied (Alternatives A and C below).
- **The flat protocol separates element state from membership.** Element
  state is fully solved by existing machinery — full-layer merge frames,
  per-row `_v` watermarks (ADR-0013/0014), `_del` tombstones, the layered
  walk (ADR-0016) — and is reused wholesale.
- **The server must hold no per-connection membership state.** v0's
  `anchor_index` and any consumer-side member set make every connection a
  memory and bookkeeping liability, and make reconnect sticky. Whatever
  concludes "in or out" must not require the server to remember what each
  client holds.
- **ADR-0018 supplies delivery**: routed groups carry the lifecycle events
  (creation, update with `publish(old) ∪ publish(new)`, delete), and its
  doctrine fixes the security boundary — delivery is authorization;
  residual conditions are presentation.
- **Every frame carries the row's full flat layer, never a diff.** The
  client index is therefore a cache, not the only copy — which is what
  makes derivation, eviction, and re-snapshotting all safe by construction.

## Decision

**Interface.** A list is a queryset assigned to a `many=True` field in
`on_connect`. Reassignment supersedes (ADR-0016's existing semantics).
Queryset slicing is the future pagination surface. That is the entire
developer surface.

**Bind-time introspection.** At assignment, the framework walks
`queryset.query.where` and `order_by` to extract the conditions (column,
lookup, value) and the ordering spec. Every condition must be either
**covered by the field's Router dimension** (ADR-0018 — delivery is its
check) or **frame-evaluable from serializer fields**; ordering columns must
be serializer fields too. Anything else fails loudly at bind, naming the
condition.

**Derived membership.** At bind the server sends the client one small
descriptor — conditions, ordering, and subscribe values where relevant.
From then on, membership is a pure function the client computes: *rows in
my index that pass the conditions, sorted by the ordering spec*. There are
no membership operations on the wire, no transition detection anywhere,
and no per-connection server state — the previous state lives in the one
place it already exists, the client. The wire carries only what it carried
before, plus the descriptor: layers, tombstones.

**Client mechanics.** `StateBuilder` grows an anchor *set* per list field
(replacing the single-anchor assumption): `state` is `null` before the
first snapshot frame, `[]` after an empty one, `T[]` in generated types.
`_del` removes the pk from the anchor set through the existing detach
path. Rows failing residuals stay in the index with their frames relayed —
so a mutable residual column flipping later toggles membership through an
ordinary update frame. Insert position is computed client-side by ordering
comparison.

**Rebind is authoritative.** On any (re)bind, the snapshot resets the
field's membership basis: index rows absent from the snapshot are demoted
to non-member cache — watermarks retained so stale frames still cannot
resurrect old state — and re-enter only via a fresh full-layer event. This
closes the offline-delete/offline-leave hole (the snapshot says who's in;
it never says who's out) and is the same rule pagination refill uses. It
is sufficient because of the connected invariant: while connected, any
event capable of qualifying a row delivers its full, fresh layer;
disconnection is precisely a break in that invariant, and the
authoritative snapshot is what re-establishes it.

**Reconnect.** Persistent socket with backoff (ported from v0's
`PersistentWebsocket`). A reconnect is a rebind over a warm index —
idempotent by watermarks, cheap by construction — and lands on any worker,
because nothing about membership is server-side.

**Recorded as future work, not built:**

- *Index eviction* — safe because the index is a cache: evict non-member
  rows unreferenced in the parents map; keep pk→`_v` watermarks after
  evicting bodies (bytes, and they keep stale frames rejected); the
  consumer-side drop of residual-failing creations (ADR-0018) keeps
  never-members out of the index; rebind compacts naturally.
- *Pagination* — slicing on assignment (`[N:M]`, introspectable via
  `query.low_mark`/`high_mark`), prev/next as reassignment. Page = live
  snapshot; the client can insert-and-trim but never grow the window, so
  refill = rebind (auto-rebind-on-shrink as candidate default). Offset
  windows drift under inserts (inherent to offset); cursor/keyset
  pagination is the blessed idiom — the cursor is a frame-evaluable
  residual with a stable boundary. The window never narrows delivery.
- *Delta reconnect* — replay-since-timestamp needs server-side event
  history, which arrives only with the cache work; a pure optimization
  under unchanged semantics, with rebind-authoritative as the permanent
  fallback.
- *Cascade-delete emission* — FK cascades bypass `ReactiveModel.delete()`
  and emit no tombstone (ADR-0013's boundary); parked, undecided.
- *Non-local-`publish` frame annotation* — a Router whose `publish` is not
  row-local (the GlobalTrack member-feed shape) delivers frames the client
  cannot judge from content alone on the leave edge; frames may need to
  carry the routing values the writer already computed. Recorded open
  point.

## Consequences

### Positive

- The interface constraint held end to end: a list is one assigned
  queryset — no new vocabulary, no glue. The framework surface got
  *smaller* relative to v0 (`auto_update`, `is_visible`, `list_instances`
  all gone).
- The wire grows exactly one small piece — the bind descriptor. Everything
  else rides existing frames: layers, tombstones, `_v` watermarks. No new
  message types, no sequence domains, no resync protocol.
- Zero per-connection membership state on the server: consumers relay,
  reconnect lands on any worker, horizontal scaling stays clean.
- Convergence by construction: full-layer frames plus watermarks make
  derivation idempotent; the snapshot-vs-live race was already solved by
  ADR-0014 and lists inherit it unchanged.
- Lists get the protocol's *uniform* consistency level — no special
  stronger guarantee to implement, no weaker one to apologize for.
- Empty vs. unloaded resolved (`null` before the first snapshot frame,
  `[]` after an empty one); generated types become `T[]`.
- Eviction is correctness-safe by construction — the index is a cache; any
  re-entering row is fully re-delivered by the event that re-qualifies it.
- One rule — rebind is authoritative — serves three needs: initial load,
  reconnect healing, pagination refill.
- Mutable residual columns need no machinery: an ordinary update frame
  re-evaluates membership client-side.

### Negative / Trade-offs

- Complexity relocates to the client: `StateBuilder` grows anchor sets,
  condition evaluation, ordering comparison, and the membership-basis
  reset. The client is now semantically load-bearing for membership —
  framework-internal code, but real code where bugs will live.
- Lookup-semantics parity: client-side condition evaluation must match
  Django's lookup semantics for every supported lookup (`exact`, `gte`,
  `in`, …) — timezone handling for datetimes, case sensitivity, type
  coercion. A mini-contract between server and generated client that must
  be tested per lookup.
- Losses are silent: no gap detection; a dropped frame means a stale row
  until its next event or rebind. Uniform with the whole protocol — but a
  wrong *list* is more visible than a stale field, so lists surface this
  exposure more.
- Failures move from import time to bind time: unsupported conditions and
  non-serialized columns error at first connect, not at import — the price
  of the bare-queryset interface (ADR-0015's reach ends where connect-time
  data begins). Loud and named, but later.
- Filter conditions and ordering columns must be serializer fields — a
  real constraint on serializer design, enforced by bind errors.
- Index growth pending eviction: non-member rows linger, bounded by
  dimension traffic (future work, with the safe-by-construction property
  above).
- The rebind-authoritative reset (demote absent rows, retain watermarks)
  is subtle client logic that must be implemented exactly — it is the only
  thing standing between offline deletions and immortal stale members.
- Cascade deletes remain a parked hole: FK cascades emit no tombstone, so
  a cascaded row is a stale member until rebind. Lists make this
  pre-existing gap louder.
- Non-local-`publish` Routers have the leave edge where the frame alone
  cannot be judged — the frame-annotation open point, recorded, not
  solved.

### Neutral

- Descriptor wire shape deferred to implementation (ADR-0002's short-key
  rule applies).
- The static tier (routing omitted, per ADR-0018) gets all of this except
  new-row delivery — one consistent behavior, minus one input.
- Reassignment keeps ADR-0016's supersede semantics unchanged; nested
  (non-anchor) state is untouched by this ADR.
- v0's `many=True` surface (`auto_update`/`is_visible`/`list_instances`)
  is deliberately not ported — replaced by ADR-0018 routing plus
  derivation.

## Alternatives Considered

### Option A: Server-authoritative membership — edge-delta ops with database-minted sequencing

Membership as an event stream: `snap`/`ins`/`rm` operations on the wire,
ordered by a per-list sequence minted on framework-owned owner rows, with
gap detection and a resync action. Its own precursor — a synthetic
container instance whose pk array is re-sent per membership change — was
rejected within it for O(n) wire per change, O(n²) under churn. The op
design was internally sound but rested on a smuggled assumption: that the
server *owns* the list as an authoritative object. Once the interface
became a bare queryset, membership stopped being an event stream — every
membership change is caused by a versioned row write, already totally
ordered by `_v` — and the sequence domain, owner table, and op vocabulary
had nothing left to do. It also held lists to a stronger loss-detection
guarantee than every other frame in the protocol. Rejected during review,
before any implementation.

### Option B: Consumer-concluded membership with explicit ops

The consumer evaluates conditions per frame and emits an explicit
insert/remove when the verdict *changes*. The wire stays explicit and the
client stays dumb — but detecting a change requires remembering the
previous verdict, so every consumer keeps a member set per connection:
v0's `anchor_index` regrown server-side, pure bookkeeping duplicating
state the client already holds because it renders it. Rejected for
accumulating per-connection server load; also what makes reconnect sticky.

### Option C: Declared query shape as the interface

`query=lambda ...: Q(...)` at class level plus `bind()` at connect. Splits
one thought across two places, invents a query-language surface over what
the queryset already says, and `bind()` was ambiguous for channels with
two lists. Rejected on the project's own standard: it compressed
complexity onto the developer instead of removing it. Its motivating
requirement — import-time shape knowledge for writers — was dissolved by
ADR-0018: with routing explicit, nothing else needs the query shape before
bind.

### Option D: Named query method with import-time symbolic tracing

`query='open_tasks'` referencing a plain method returning a queryset,
traced at import by calling it with marker objects. Django-native surface,
import-time failures, shape in code — but the tracing is clever magic with
a real constraint (query methods must build unconditionally), and like
Option C its raison d'être evaporated once routing became an explicit
declaration. Bare assignment plus bind-time introspection covers
everything with no magic.

### Option E: Reconnect via event replay (v0's `last_update`)

Replay everything since a timestamp on reconnect. Requires server-side
event history, which v0 had (Mongo) and the rebuild deliberately does not
yet — and even with history it is an optimization, not a semantic:
rebind-authoritative snapshots are correct without it and remain the
permanent fallback. Recorded as future work enabled by the cache work.

### Option F: Server-maintained sliding window for pagination

The consumer tracks the full ordered pk list per connection and ships
boundary rows on window crossings. Exact sliding windows, at the price of
per-connection ordering state — Option B in a pagination costume.
Rejected; page = live snapshot, refill = rebind.

## References

- ADR-0018 — Router-based delivery; the doctrine (delivery is
  authorization, residuals are presentation) that makes client-side
  derivation safe.
- ADR-0013 / ADR-0014 — `_v` minting and client watermarks; the total
  order that lets row writes carry membership.
- ADR-0016 — layered delivery, stubs, supersede-on-reassignment, and the
  `StateBuilder` eviction scope this ADR's index growth lands in.
- ADR-0015 — compile-time derivation; its reach ends at connect-time data,
  which is why list-shape failures are bind-time.
- `packages/react/src/StateBuilder.ts` — single-anchor assumption replaced
  by anchor sets.
- `rxdjango-0/rxdjango-react/src/PersistentWebsocket.ts`,
  `rxdjango-0/rxdjango/channels.py` — v0 reconnect and `many=True`
  baselines.
