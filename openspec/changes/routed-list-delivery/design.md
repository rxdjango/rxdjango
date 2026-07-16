# Design: routed-list-delivery

## Context

Cycle 1 built the static queryset tier: snapshot, client-derived
membership from the `q` descriptor, rebind-authoritative reset, warm
reconnect. What's missing is exactly what ADR-0018 exists for: delivering
row events to connections with *no prior relationship* to the row — the
creation, and the update that moves a row into a watched list. The Router
(`publish(instance)` / `subscribe(channel)`) is the accepted answer;
v0's per-consumer `is_visible`/`auto_update` scans are deliberately not
ported.

The client side is nearly done already: derivation, ordering, leave-edge
handling, and watermark idempotence all shipped in cycle 1. This change
is mostly server-side plumbing plus one client rule (basis growth).

## Goals / Non-Goals

**Goals:**

- Router surface: class form, `ColumnRouter` sugar, `BroadcastRouter`,
  declaration-time validation, `None` filtering.
- Lifecycle broadcasts through dimension groups with the gated pre-image
  read; dedup across declarations.
- Import-time registration + framework-owned autodiscovery in every
  process type.
- Consumer dimension-group joins at bind, relay tagging, the
  creation-drop optimization, `rebind(field)`.
- Client basis growth for live fields (`l` marker); protocol 0.4.0.
- Routed example app + e2e.

**Non-Goals (all recorded future work in ADR-0018/0019):**

- Residual-traffic digest (Bloom filter), index eviction, pagination,
  delta reconnect, cascade-delete emission.
- Non-local-`publish` frame annotation (the GlobalTrack leave-edge open
  point) — custom Routers whose dimension is not frame-evaluable keep
  that recorded limitation.
- Removing per-instance-group redundancy for routed anchors (see D4).

## Decisions

### D1: Router registry keyed by (model, dimension), populated at declaration

Declaring `routing=` on a field registers `(model class, router)` in a
module-level registry inside `rxdjango_model` (beside the existing
reactive registry). Dimension identity for dedup is
`(model label, router key)` — `ColumnRouter`'s key is its column name; a
custom Router's key defaults to its class's dotted path. Group names are
`rx.route.<model_label>.<router key>.<hash of value>` inside the channel
layer's existing namespace; values are hashed so opaque tuples work and
group names stay channel-layer-legal. Two channels declaring
`routing='project_id'` for the same model produce the same groups — one
broadcast per distinct value in use.

### D2: Write path — `publish(old) ∪ publish(new)` with a gated pre-image

`ReactiveModel.save()` already runs write + version bump atomically and
defers broadcast to commit. For models with registered routers, the save
path additionally: (a) determines each router's input columns
(`ColumnRouter` knows its column; custom Routers declare `columns`, or
omit it to force a full-row pre-image); (b) if the save is an update and
`update_fields` intersects the input columns (or is None), reads the old
row's input columns inside the atomic block; (c) on commit, broadcasts
the new layer to the groups of `publish(old) ∪ publish(new)` (creation:
`publish(new)` only; delete: tombstone to `publish(row)`), with `None`
filtered from every returned set. The old-side frame *is* the leave
signal — no membership tracking anywhere.

### D3: Consumer bind joins dimension groups; relay tags the field

At bind of a routed field, the consumer runs `subscribe(channel)`,
filters `None`, and joins the dimension groups (leaving stale ones on
rebind/clear, extending cycle 1's group bookkeeping). Dimension-group
events relay to the client as ordinary merge frames tagged with the
field, exactly like per-instance events. The consumer MAY drop a
*creation* that fails the field's frame-evaluable residuals (it knows
`w` from bind-time introspection); it never drops updates.
`rebind(field)` = re-run subscribe + refresh joins + re-run the snapshot
walk (which re-emits `q`, giving the client its authoritative reset for
free).

### D4: Duplicate delivery is tolerated in v1, not prevented

A connection may hold a row through its per-instance group *and* its
dimension group; an update then arrives twice with the same `_v`, and the
client's watermark rule ("apply only if `_v` exceeds") makes the second
a no-op. Correctness by construction, small bandwidth cost. ADR-0018's
expected optimization — skipping per-instance joins for routed anchors —
is deferred: it interacts with nested-layer delivery and deserves its own
verification, and v1 keeps one delivery mechanism per concern instead of
a conditional join matrix.

### D5: Client basis growth keyed on the `l` marker

The descriptor gains `l: true` for routed fields. StateBuilder's rule:
on a full anchor-type layer arriving for a live field, if the row passes
`w`, admit it to the basis (static fields keep never-grow). Everything
downstream — ordering, new array identity, leave on failing conditions,
demotion at rebind, watermarks — is cycle 1 machinery unchanged. The
protocol version bumps to 0.4.0.

### D6: Autodiscovery is framework-owned

`rxdjango`'s `AppConfig.ready()` imports each installed app's `channels`
module (tolerating absence). Since every Django process type runs
`django.setup()`, registration happens in web workers, task workers, and
management commands alike — ADR-0018's hard requirement satisfied by
installing the app, not by per-app wiring. If an autodiscovery hook
already exists for websocket routing, this extends it rather than adding
a second mechanism.

### D7: Bind validation is additive only

Cycle 1's introspection rules stand: conditions must be frame-evaluable,
AND-only, serializer-local. The Router does not relax them in v1 — a
condition on a non-serialized column remains a bind error even when the
Router's dimension covers it, because the leave edge needs the client to
judge the frame (ADR-0019's recorded open point). The mirror contract
(`publish` and `subscribe` agreeing on the dimension's meaning) is
unverifiable by the framework, per ADR-0018 — the class form keeps both
halves adjacent and unit-testable; the column sugar is the recommended
default.

### D8: Example — live task board

One routed example app (`routing='project_id'` column sugar on a task
list), docgen pipeline as usual. E2e: creation appears live at the
ordered position; dimension move removes from one client and appears for
another; residual flip still toggles; static-tier example unaffected.
Two-connection isolation is asserted at the integration tier (cheaper
and more precise than dual-browser e2e), with the e2e covering the
single-client live-creation experience.

## Risks / Trade-offs

- [Mirror-contract violation under-delivers silently] → structural
  mitigations only (ADR-0018): both halves adjacent, unit-testable
  together; column sugar as default; document that Router code reviews
  as security code.
- [Missed autodiscovery in an exotic process type under-broadcasts] →
  framework-owned discovery in `AppConfig.ready()`; integration test
  exercising a management-command writer.
- [Pre-image read adds a per-update query for routed models] → gated by
  `update_fields` and input columns; documented as the accepted
  `db_index`-style cost.
- [Duplicate delivery inflates bandwidth on hot rows] → bounded (2× worst
  case per row event), converges by `_v`; the per-instance-join removal
  is the recorded follow-up.
- [Creation-drop optimization mistakenly dropping an update] → the drop
  path keys on the broadcast's create/update discriminator set by the
  writer, not on heuristics; covered by an integration test (failing
  update must still relay).

## Open Questions

None blocking. Group-name hashing details (algorithm, length) are
implementation constants inside D1's naming scheme.
