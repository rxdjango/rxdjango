# 0013. Use a `ReactiveModel` base class to weld per-row versions to writes

- **Date:** 2026-05-14
- **Status:** Active
- **Deciders:** Luis Fagundes

> **Implementation note.** The version column described below as `version` is
> named `_v` in the shipped code (`ReactiveModel._v`), keeping it visually
> distinct from application fields and consistent with the `_type` / `_del`
> wire markers. The `RETURNING` / `LAST_INSERT_ID` write path is implemented in
> `ReactiveModel.save()` / `delete()` (package `rxdjango_model`); the broadcast
> is driven through the Channels channel layer via the reactive registry. The
> save path wraps the user write and the version bump in one `transaction.atomic()`
> block so the row lock spans both, rather than welding them into a single
> statement.

## Context

RxDjango's core promise is that subscribed clients see the same state that
ended up in the database. To deliver that promise the framework runs two
operations whenever a client connects to an instance:

1. **Fetch** the instance state (from the DB or a cache).
2. **Subscribe** to the event stream for that instance.

These two operations cannot be made atomic at the application level. Whichever
order they run in, there is a window in which a concurrent writer can mutate
the row:

- *Fetch then subscribe:* a write that commits between the fetch and the
  subscription is missed entirely — the client starts out stale and never
  recovers.
- *Subscribe then fetch:* the fetch may read a row that is newer than some of
  the queued events, and the client cannot tell which queued events are
  already represented in the snapshot it just received.

The standard fix in sync systems (Replicache, Linear, Firestore, Convex) is a
per-row monotonic version. The client subscribes first, fetches a snapshot
that carries a version, and uses the version as a high-water mark to discard
events it has already seen. For this to be correct, two invariants must hold:

1. **The version is assigned by the database**, atomically with the write. If
   the application increments in Python, two racing clients can both read
   `v=5` and both write `v=6`, producing two distinct broadcasts that claim
   the same version.
2. **The broadcast payload and version come from the same write.** A version
   that was minted by one transaction but paired with a serialized snapshot
   taken at a different point in time will mislead the client. In the worst
   case the framework broadcasts `(state_A, v=7)` while the row at version 7
   actually contains `state_AB` — the client picks one event, silently
   discards the other, and ends up out of sync with the database.

Concretely, a "fire-and-forget" implementation that bumps the version with a
trigger and reads it back from a `post_save` signal handler **breaks
invariant 2** in Django's default autocommit mode: by the time `post_save`
fires, the row lock has been released, and a concurrent writer can have
already bumped the version further. The `SELECT` returns the wrong number.

Closing this race requires reading the version back **in the same statement
as the UPDATE** — `RETURNING version` on PostgreSQL, `LAST_INSERT_ID(version
+ 1)` on MySQL. The row lock then guarantees the returned value belongs to
this write.

A trigger-plus-signal architecture *can* be made correct by requiring all
reactive writes to happen inside `transaction.atomic()` (so `post_save` runs
while the row lock is still held), or by installing a connection-level SQL
rewriter that appends `RETURNING` to every UPDATE against a registered table.
Both options were evaluated and rejected — see *Alternatives Considered*.

## Decision

We will ship reactivity as a **`ReactiveModel` abstract base class** that
developers inherit explicitly. The base class owns a `version` field and
overrides `_do_update` / `_do_insert` to perform the atomic versioned write
with per-backend SQL (`RETURNING` on PostgreSQL, `LAST_INSERT_ID` on MySQL),
then schedules the broadcast via `transaction.on_commit`. It also overrides
`delete()` so that a deletion mints a final version for the row and
broadcasts a versioned delete event — without which a client cannot tell a
stale snapshot apart from a live row and could resurrect a deleted instance.

Inheritance is the *only* supported path. There is no signal-based fallback
for unmodified models, because such a fallback would silently violate the
framework's central invariant under concurrent writes.

## Architecture

### Developer surface

```python
from rxdjango.models import ReactiveModel

class Memo(ReactiveModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
```

The `version` field is contributed by `ReactiveModel`, appears in migrations
automatically, and is not editable from user code. No `save()` override, no
signal `connect()`, no `transaction.atomic()` requirement, no broadcast
plumbing.

### Write path

`ReactiveModel` overrides `_do_update` and `_do_insert` (the hook points
called by `Model.save_base()`). The override:

1. Dispatches on the connection vendor.
2. Issues a single statement that performs the user's write **and**
   increments and returns the new version:
   - **PostgreSQL:** `UPDATE ... SET ..., version = version + 1 RETURNING
     version` via `connection.cursor()`.
   - **MySQL:** `UPDATE ... SET ..., version = LAST_INSERT_ID(version + 1)`
     followed by `cursor.lastrowid` (no extra roundtrip — the value is on
     the OK packet).
3. Assigns the returned value to `self.version`.
4. Looks up the registered serializer for `type(self)` from the framework's
   `Model → Serializer` registry (populated at `AppConfig.ready()` from
   channel declarations).
5. Calls `transaction.on_commit(lambda: broadcast(serializer(self).data,
   self.version))`. `on_commit` adapts to context: if the caller is inside
   `atomic()`, the broadcast fires on commit; if not, it fires immediately.

### Delete path

A deletion removes the row, so there is no row left to carry an incremented
`version`. But the delete event still needs a version: a client holding an
in-flight snapshot must be able to discard it in favour of the delete,
otherwise a stale snapshot arriving after the delete event silently
resurrects the instance.

`ReactiveModel` overrides `delete()`. Django's `Collector` already runs the
deletion inside `transaction.atomic()`, so the row lock is held across the
statements below:

1. Dispatches on the connection vendor.
2. Reads the row's current version **in the same statement as the DELETE**:
   - **PostgreSQL:** `DELETE FROM tbl WHERE id = ? RETURNING version`.
   - **MySQL:** no `RETURNING` on `DELETE`; issues `SELECT version FROM tbl
     WHERE id = ? FOR UPDATE` immediately before the `DELETE`, both inside
     the `Collector`'s atomic block.
3. The returned value `v` is the version of the last committed update. The
   delete event is broadcast at **`v + 1`**. This value is final: nothing can
   write the row after it is gone, and the row lock serialized this delete
   against any concurrent update, so `v + 1` is provably the highest version
   any client will ever see for this row.
4. Calls `transaction.on_commit(lambda: broadcast_delete(type(self),
   self.pk, v + 1))`.

Clients keep the highest version per row as a watermark and discard any
snapshot or event `≤` it; a delete at `v + 1` therefore always wins over the
`v`-or-older snapshot it races.

### Race resolution

Two concurrent writers to the same row are serialized by the row-level lock
acquired by the UPDATE:

- T1: `UPDATE ... RETURNING version` → version=6. T1 holds the row lock until
  commit.
- T2: `UPDATE ... RETURNING version` → blocks on T1's lock.
- T1 commits, schedules broadcast `(state_T1, 6)`.
- T2 unblocks, re-reads `OLD.version = 6`, increments to 7, returns 7,
  commits, schedules broadcast `(state_T2, 7)`.

Broadcast order matches commit order, and every `(payload, version)` pair
came from the same atomic statement. Clients keep the highest version they
have seen and discard anything `≤` that watermark.

### Scope

The version is **per-row**. RxDjango subscriptions are per-instance in the
new architecture; total ordering across rows is not required. Each reactive
model carries its own independent counter.

### Limitations

- Requires inheritance. Models the developer does not own (third-party
  packages, contrib apps) cannot be made reactive in place. Workaround: a
  thin proxy or a project-owned wrapper model.
- Requires the `version` column to exist. Migrations handle this for new
  reactive models; retrofitting an existing model adds a `BIGINT` column.
- SQLite is not supported as a reactive backend. SQLite's single-writer model
  is fundamentally incompatible with multi-client sync; the framework treats
  SQLite as fetch-only.
- The delete path is only versioned for a *direct* `instance.delete()`.
  Cascade deletes (a parent deletion cascading to children) and
  `QuerySet.delete()` are executed by Django's `Collector` as a bulk `DELETE`
  that bypasses the per-instance `delete()` override, so they emit no
  versioned delete event. **This must be documented:** delete a reactive
  instance with `instance.delete()`; rows removed by cascade or
  `QuerySet.delete()` will not broadcast and clients subscribed to them go
  stale until a `ReactiveQuerySet` covers the bulk paths.

## Consequences

### Positive

- The framework's central invariant — *broadcast state matches DB state at
  the broadcast's version* — is enforced at the lowest possible level and
  cannot be bypassed by user code.
- One DB statement per write, no extra `SELECT` roundtrip.
- Inheritance self-documents which models participate in reactive sync; a
  reader of the source sees `class Memo(ReactiveModel)` and immediately
  understands the contract.
- No coupling of correctness to user transaction discipline — works in
  autocommit, inside `atomic()`, inside `ATOMIC_REQUESTS`, and from
  management commands without special handling.
- Per-backend SQL is localized to one method on one class.

### Negative / Trade-offs

- Reactive models cannot be third-party Django models without subclassing or
  proxying.
- The framework owns `_do_update` / `_do_insert` and `delete()` on reactive
  models, which constrains user overrides of those methods (rare in
  practice).
- Per-backend dispatch (PostgreSQL vs MySQL) lives in the framework. Adding a
  new backend requires implementing the same primitive there.
- `QuerySet.update()` and `bulk_update()` bypass `_do_update`, and
  `QuerySet.delete()` and cascade deletes bypass the `delete()` override, so
  none of them produce broadcasts. Documented as "use `save()` and
  `instance.delete()` for reactive writes" until a `ReactiveQuerySet` covers
  the bulk paths.

### Neutral

- The `version` column adds 8 bytes per row on reactive tables.
- Developers see `version` in the database and in migrations; it is
  read-only from Python.
- The framework's model registry is populated from channel declarations at
  app-ready time — no decorator on the model itself.

## Alternatives Considered

### Option A: Increment in Python on a regular field

`instance.version += 1; instance.save()`. Simple, no backend-specific SQL.

**Rejected** because it does not satisfy invariant 1. Two racing writers can
both read `v=5` and both write `v=6`, producing two broadcasts that claim the
same version with different payloads. The DB row reflects last-write-wins,
but neither broadcast is guaranteed to match it. This corrupts the
client-side state silently.

### Option B: Database triggers + `post_save` signal `SELECT`

A migration installs a `version` column and a `BEFORE UPDATE` trigger that
bumps it. A `post_save` signal handler issues `SELECT version FROM tbl WHERE
id = ?` and broadcasts the result. Fully external to the model declaration.

**Rejected** because it does not satisfy invariant 2 under Django's default
autocommit. The signal fires *after* the implicit transaction commits and
the row lock is released, so a concurrent writer can have already bumped the
version further. The `SELECT` then returns a number that does not correspond
to the state this signal is about to broadcast — producing two events that
claim the same version with different payloads, or one event whose payload
is older than its version implies.

### Option C: Triggers + `post_save` + mandatory `transaction.atomic()`

Same as Option B, but the framework requires reactive writes to occur inside
`transaction.atomic()`. Inside an atomic block, `post_save` fires while the
row lock is still held, and the signal's `SELECT` sees the correct version.

**Rejected** because it couples framework correctness to user discipline.
One forgotten `atomic()` — in a management command, a Celery task, a test
fixture — silently corrupts the client view with no error and no obvious
symptom until production load. A framework should not have invariants that
break depending on whether the caller remembered to wrap a block.

### Option D: Connection-level SQL rewriting

Install a global `connection.execute_wrapper` (or a custom DB backend) at
app-ready time. The wrapper detects UPDATEs against registered reactive
tables and appends `RETURNING version` (PostgreSQL) or wraps with
`LAST_INSERT_ID(version + 1)` (MySQL). The trigger still owns the increment;
the wrapper welds the read to the same statement. Fully external; works for
`save()`, `QuerySet.update()`, `bulk_update()`, raw SQL, admin saves, and
shell saves uniformly.

**Rejected** for cost/benefit reasons. The mechanism is deep magic and
brittle to Django internals — query rewriting at the cursor layer interacts
with prepared statements, the Django query compiler, third-party DB router
middleware, and any other `execute_wrapper`. The framework writes the same
per-backend SQL as Option E (the chosen one), but injects it via global
interception rather than a class method. The user-visible saving is exactly
one line of inheritance, and the framework gains a difficult-to-debug global
side-effect. The tradeoff does not favor it.

### Option E: Tiered — signals by default, base class opt-in

Ship both Option B (signal-based, works on any model) as the default and
Option E (`ReactiveModel`) as an opt-in for users who want race protection.
Mirrors DRF's `Serializer` / `ModelSerializer` split.

**Rejected** because the default would silently violate the framework's
central promise under concurrent writes. The framework's value proposition
is consistency between client and DB; a default mode in which that
consistency holds only under single-writer load is a footgun, not a
convenience. The signal path is *also* slower per save (extra `SELECT`),
so the convenience framing does not even carry a performance argument.

## References

- Conversation thread leading to this decision (2026-05-14).
- PostgreSQL `RETURNING` clause:
  https://www.postgresql.org/docs/current/dml-returning.html
- MySQL `LAST_INSERT_ID(expr)`:
  https://dev.mysql.com/doc/refman/8.0/en/information-functions.html#function_last-insert-id
- Replicache sync model (per-row version watermarks):
  https://doc.replicache.dev/concepts/how-it-works
