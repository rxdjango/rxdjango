# 0018. Route live list delivery through per-field Router declarations

- **Date:** 2026-07-15
- **Status:** Active
- **Deciders:** Luis Fagundes

## Context

A `rx.model(Serializer(many=True))` list must show rows the client has never
seen: a newly created row cannot be delivered through per-instance broadcast
groups — no consumer has joined a group for a pk that did not exist — and the
same applies to an update that moves an existing row *into* a list the
connection watches. Something must carry row events to connections with no
prior relationship to the row.

Forces:

- **v0's baseline does not scale.** v0 answered with per-consumer checks
  (`is_visible`, `auto_update`): every connection evaluated every candidate
  row, typically with a database query each. N connections meant N duplicate
  checks per write; membership had no shared delivery structure
  (`rxdjango-0/rxdjango/channels.py`).
- **Coarse broadcast is a performance killer.** One group per model, with
  every list-holding consumer checking candidates in memory, delivers every
  creation of the model to every such consumer; irrelevant traffic dominates
  at scale.
- **Automatic precise routing is asymptotic work.** Deriving delivery from
  query analysis means re-engineering Django's query machinery backwards —
  either an invented declaration language or a runtime shape registry with
  cross-process staleness.
- **The goal is performance through explicit automation.** Explicit is
  better than implicit; the precedent is `db_index`: Django does not infer
  access paths by watching queries — the developer declares them, and the
  framework does everything mechanical downstream.
- **Routing is subscription topology, a channel concern.** It describes how
  observers are organized, not what a row is. Two channels legitimately route
  the same model differently: a project page routes tasks by `project_id`, a
  developer page routes the same tasks by `assignee_id`. The declaration
  therefore cannot live on the model.
- **The GlobalTrack case sets the bar.** Runs visible through Project
  membership (N:N) under complex permission arrangements: the routing
  dimension is not a column, and choosing between fan-out-on-read and
  fan-out-on-write depends on cardinalities only the application knows —
  both sides of routing must be developer code.
- **Writers are arbitrary processes** (web workers, task workers, management
  commands). Whatever routing consults must be plain imported code — no
  runtime registry, no shared discovery state.

## Decision

`rx.model(Serializer(many=True), routing=...)` takes a **Router**: two
functions forming one reviewable contract.

- `publish(instance)` → the group values a saved row announces to
  (writer side);
- `subscribe(channel)` → the group values a connection listens on
  (bind side).

Sugar forms are built-in trivial Routers: a column string
(`routing='project_id'`) is a `ColumnRouter`; the explicit broadcast
firehose is a framework-provided `BroadcastRouter` (the constant function on
both sides). `routing=None` is invalid. **Omitted routing means a static
list**: snapshot plus updates and deletes to known rows, no new-row
delivery. Router values are opaque (tuples work), so composite dimensions
need no special support; only the string sugar is single-column.

**`None` is never a group value.** It is filtered from whatever `publish()`
or `subscribe()` returns: a row whose routing column is null is simply not
announced. An empty `publish()` set means the row announces to no one; an
empty `subscribe()` set means the connection listens on nothing. Custom
Routers inherit the rule for free.

**The Router is the model's lifecycle delivery dimension**, not a creation
mechanism:

- creations broadcast to `publish(row)`;
- updates broadcast to `publish(old) ∪ publish(new)` — requiring a narrow
  pre-image read of only the Router's input columns, inside the existing
  transaction, skipped when `update_fields` cannot affect them;
- deletes send the tombstone to `publish(row)`.

The old-side delivery of an update is the stateless **leave signal**: a
connection subscribed to the old value receives the frame that disqualifies
the row, with no membership tracking anywhere.

Declarations register at import. **Channels autodiscovery runs in
`AppConfig.ready()` in every process type** — a hard requirement, because a
writer that skips it silently under-broadcasts.

**The security doctrine.** A connection receives every event for rows whose
`publish()` values intersect its `subscribe()` values — that sentence is the
entire answer to "who can learn about what." Delivery is authorization; the
client is never trusted to hide what it holds. Authorization must be
expressed as routing dimensions; filter conditions not covered by routing
(residuals) are presentation, evaluated client-side, shipped to the client
with their values visible — no secrets in residuals. Router code reviews as
security code; every firehose is greppable (`BroadcastRouter`).

**Subscriptions are bind-time snapshots.** `subscribe()` runs at bind;
changes to the underlying relation (a user joins a project) take effect on
rebind, and a `rebind(field)` lever re-runs it. The **mirror contract** —
`publish` and `subscribe` must agree on the dimension's meaning — cannot be
verified by the framework; under-delivery is a silent miss. The class form
keeps both halves adjacent and unit-testable together; the column sugar is
the recommended default.

Consumers may drop residual-failing *creations* as a bandwidth optimization
(safe: a row the client never held needs no leave signal) — never updates.

Hard limits, recorded: the group algebra expresses "row → finite values"
meeting "connection → finite values" and nothing finer — arbitrary
per-(row, user) predicates are inexpressible, with per-user publish as the
nearest approximation. The column sugar requires a concrete local column.
Only `save()`/`delete()` speak; bulk operations remain out of scope per
ADR-0013.

## Consequences

### Positive

- Precise delivery for one word of declaration: `routing='project_id'` buys
  exact scoping; a creation costs one broadcast per *distinct dimension in
  use* (deduped across all fields and channels declaring it), never per
  connection, never per list.
- The cost model is countable on fingers: no hidden scans, no invisible
  fan-out; delivery topology is code, visible in diffs and code review.
- Both fan-out strategies are expressible and the choice belongs to the
  application: resolve at subscribe (cheap writes, connect-time query) or
  amplify at publish (cheap connects, write pays) — ten reviewable lines
  either way.
- No runtime registry anywhere: routing is imported code, correct in every
  process type; writers stay dumb.
- The security surface is explicit and auditable: the delivery contract is
  one sentence; Router code reviews as security code; every firehose is
  greppable.
- Lifecycle uniformity: creation, update, and delete ride the same
  dimension; `publish(old) ∪ publish(new)` delivers enter and leave to both
  audiences with one broadcast pair.
- Expected (to verify at implementation): per-instance groups become
  redundant for list anchors — consumer group membership drops from
  O(rows relayed) to O(subscribed dimension values).
- High-cardinality dimensions are cheap: groups are cheap sets, an
  empty-group send is a no-op, dead groups expire.

### Negative / Trade-offs

- The mirror contract is unverifiable by the framework; a
  `publish`/`subscribe` disagreement is a silent miss. Mitigations are
  structural only: both halves adjacent in one class, unit-testable
  together, column sugar as the recommended default.
- Channels autodiscovery in every process is a hard requirement; a writer
  that skips it under-broadcasts silently. Loud-failure detection deserves
  real effort at implementation time.
- Updates of routed models pay a narrow pre-image read (Router input
  columns only, `update_fields`-gated) — a real per-write cost added by
  lists.
- Subscriptions are bind-time snapshots: membership-relation changes take
  effect only on rebind — a documented semantic with an explicit lever,
  deliberately not auto-magic.
- Residual conditions ship to the client with their values visible; filter
  values are disclosed by design — secrets must never appear in residuals.
- Delivery granularity is coarser than the queryset **by exactly the
  conditions the developer leaves out of the dimension**. Exact-match
  conditions can be promoted into composite dimensions (leave signals
  arrive statelessly via `publish(old)`-side delivery); range conditions
  can be banded by a custom Router (publish the row's bucket, subscribe to
  the buckets overlapping the window); the irreducible residual traffic is
  bandwidth, not correctness, with a lossy consumer-side digest (Bloom
  filter of relayed-passing pks; one-sided error — false positives waste a
  relay, never lose a leave signal; reset at rebind) recorded as future
  work. The pathological case — huge dimension, thin residual slice — is
  precisely the signal to promote.
- The group algebra is the hard boundary: arbitrary per-(row, user)
  predicates are inexpressible; the nearest approximation is per-user
  publish, paying write amplification.
- The developer must think about delivery when designing a list — the
  `db_index` burden, accepted deliberately; there is no middle ground
  between a declared dimension and an explicit firehose, also deliberate.

### Neutral

- Omitted routing = static list: a legitimate zero-cost tier; its failure
  mode (new rows don't appear) is immediately visible in development.
- Same dimension declared many times dedupes to one group set; group naming
  is an implementation detail inside the channel layer's existing
  namespace.
- The broadcast singleton's exact spelling is deferred to implementation.
- Bulk operations remain out of scope per ADR-0013's line; cascade-delete
  event emission is parked separately.

## Alternatives Considered

### Option A: v0's per-consumer visibility checks (`is_visible` / `auto_update`)

Every connection evaluates every candidate row, typically with a database
query each. Rejected: N connections mean N duplicate checks per write —
delivery has no shared structure, and the check cost lives on the hot path.
This is the design the Router replaces.

### Option B: Coarse per-model creation group

One group per model; every consumer holding any list of that model joins it
and checks candidates in memory. Zero declaration, zero infrastructure.
Rejected: a performance killer even with in-memory checks — every consumer
hears every creation of the model, and irrelevant traffic dominates at
scale.

### Option C: Automatic precise routing derived from the queryset

The framework analyzes filters and routes writes to matching lists itself.
Two variants: (1) a declared query shape (`query=lambda ...: Q(...)`)
decomposed into routing atoms at import — rejected as an invented query
language that compresses complexity instead of removing it, saying again
what the queryset already says; (2) bind-time introspection feeding a
shared shape registry (database table, writer-side caching) — rejected
because routing knowledge becomes runtime state with staleness windows and
deploy skew, and the general form is asymptotic work: re-engineering
Django's query machinery backwards. The surviving distinction: bind-time
introspection of *conditions* still exists (for residual checks and the
client descriptor); what is rejected is deriving *delivery* from it.

### Option D: Routing declared on the model

`class Rx: routing = [...]` on the `ReactiveModel`. Writer-side trivially
safe — importing the model guarantees the declaration is loaded. Rejected
on semantics: routing is subscription topology, a channel-layer concern,
and two channels legitimately route the same model differently. The price
of the channel-level home — writers must autodiscover `channels.py` — is
accepted and recorded as a hard requirement.

### Option E: Column strings only, no Router abstraction

Rejected as the sole mechanism by the GlobalTrack case: a dimension reached
through an N:N (Runs visible via Project membership) is not a local column,
and the fan-out-on-read vs fan-out-on-write choice it forces depends on
cardinalities only the application knows — both sides of routing must be
developer code. The column string survives as sugar for `ColumnRouter`.

### Option F: `routing=None` as the broadcast declaration

Rejected: it collides with the protocol-level rule that `None` is never a
group value (null = not announced), inverting the meaning of the same
symbol between value level and declaration level — and the most expensive
delivery choice deserves the most visible, greppable declaration
(`BroadcastRouter`).

### Option G: Server-enforced residuals at the consumer

Enforce non-routed filter conditions by having the consumer suppress
non-matching frames, making residuals a security boundary. Rejected:
suppression either breaks leave detection (the failing frame *is* the
leave signal) or requires per-connection member tracking — v0's state
creeping back through the security door. The doctrine instead assigns
authorization to routing dimensions exclusively; the single safe exception
(dropping residual-failing creations) is kept as a bandwidth optimization,
explicitly not a security mechanism.

## References

- ADR-0003 — the v0 `ContextChannel` surface this design inherits from and
  the `channels.py` discovery convention it relies on.
- ADR-0010 — `rx.model` reactive fields, where `routing=` lives.
- ADR-0013 — `ReactiveModel` write path the broadcasts and pre-image read
  extend; the bulk-operation scope line reaffirmed here.
- ADR-0016 — layered delivery and the consumer relay (join-before-send)
  this delivery path composes with.
- `rxdjango-0/rxdjango/channels.py` — v0's `is_visible`/`auto_update`
  baseline.
