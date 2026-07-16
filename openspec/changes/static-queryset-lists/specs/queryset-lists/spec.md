# Queryset Lists (delta)

## ADDED Requirements

### Requirement: A list is a queryset assigned to a `many=True` field

The developer surface for a list SHALL be exactly ADR-0019's interface: a
plain Django queryset assigned to a `many=True` `rx.model` field in
`on_connect`. No declaration language, no new verbs. Reassignment
supersedes per `model-state`'s existing semantics. Without a routing
declaration the field is a **static list** (ADR-0018): snapshot plus
updates and deletes to known rows; rows created after the snapshot do not
appear until a rebind.

#### Scenario: Bare queryset binds

- **WHEN** `on_connect` runs `self.tasks = Task.objects.filter(status='open').order_by('-created_at')`
- **THEN** the client receives the field's snapshot and `channel.tasks` derives to the matching rows in descending creation order

#### Scenario: New row does not appear in a static list

- **WHEN** a row matching the queryset's conditions is created after the snapshot
- **THEN** the connected client's list is unchanged until the field is rebound

### Requirement: Bind-time introspection validates conditions and ordering

At assignment the framework SHALL walk `queryset.query.where` and the
ordering spec, extracting `(column, lookup, value)` conditions. Every
condition column and every ordering column MUST be a field of the anchor
serializer's output, every lookup MUST be in the supported set, condition
values MUST be JSON-serializable, and the condition tree MUST be a
conjunction (AND) of simple conditions. Any violation — a non-serialized
column, an unsupported lookup, a related-field (join) lookup, or OR/NOT
structure — SHALL raise loudly at bind, naming the offending condition.

#### Scenario: Non-serialized column rejected

- **WHEN** the queryset filters on `internal_flag`, which is not a field of the anchor serializer
- **THEN** the bind fails with an error naming `internal_flag`

#### Scenario: Unsupported structure rejected

- **WHEN** the queryset's where clause contains an OR of two conditions
- **THEN** the bind fails with an error identifying the unsupported structure

### Requirement: The bind descriptor resets the membership basis

Each (re)bind snapshot SHALL deliver a descriptor — the introspected
conditions and ordering spec — attached to the snapshot's anchor frame
(wire shape per `wire-protocol`). On receiving it, the client SHALL
atomically reset the field's **membership basis** to exactly the anchor
rows carried by that frame: index rows absent from the new basis are
demoted to non-member cache with their `_v` watermarks retained, and
re-enter only through a later authoritative snapshot. There SHALL be no
membership operations on the wire and no per-connection membership state
on the server.

#### Scenario: Rebind drops offline-deleted rows

- **WHEN** a client holds rows 1–3, disconnects, row 2 is deleted (no tombstone observed), and the client rebinds
- **THEN** the new snapshot carries rows 1 and 3 and the derived list no longer contains row 2

#### Scenario: Demoted row cannot be resurrected by a stale frame

- **WHEN** a row was demoted at rebind and a frame older than its retained watermark arrives
- **THEN** the frame is discarded and the row stays out of the list

### Requirement: Membership is derived client-side

List membership SHALL be a pure client-side function: the rows of the
field's membership basis that pass the descriptor's conditions, sorted by
its ordering spec. Rows failing conditions SHALL remain in the index with
frames still applied, so a mutable column flipping later toggles
membership through an ordinary update frame. A `_del` tombstone SHALL
remove the row from the basis through the existing detach path. Each
membership or order change SHALL produce a new array identity and publish
a new state version.

#### Scenario: Residual flip removes then restores a row

- **WHEN** a member task's update frame arrives with `status: 'closed'` and a later frame arrives with `status: 'open'`
- **THEN** the task leaves the derived list on the first frame and re-enters it, correctly positioned, on the second

#### Scenario: Deleted member disappears

- **WHEN** a `_del` tombstone arrives for a member row
- **THEN** the row leaves the derived list

#### Scenario: Order tracks updated columns

- **WHEN** ordering is `-priority` and a member's update frame raises its priority above the current head
- **THEN** the derived list re-sorts with that row first

### Requirement: List state distinguishes unloaded from empty

A `many=True` field's state SHALL be `null` before the first snapshot
anchor frame, `[]` after a snapshot whose anchor row set is empty, and the
derived array thereafter. Anchor rows arrive with full layers in the
snapshot, so list elements are never unloaded stubs (nested relations
inside them stub as usual per `model-state`).

#### Scenario: Empty is not unloaded

- **WHEN** a queryset matching zero rows is bound
- **THEN** `channel.tasks` is `null` until the snapshot anchor frame arrives and `[]` immediately after it

### Requirement: Condition evaluation matches Django lookup semantics

The client SHALL evaluate the supported lookups — `exact`, `in`, `gt`,
`gte`, `lt`, `lte`, `isnull` — with the same verdicts Django produces for
the serialized field values, including comparisons on DRF's ISO-8601
datetime strings. This parity SHALL be covered by tests per lookup.

#### Scenario: Datetime boundary agrees with the server

- **WHEN** the descriptor carries `created_at gte <iso timestamp>` and an update frame carries a `created_at` exactly equal to it
- **THEN** the client's verdict is membership, matching Django's `gte`
