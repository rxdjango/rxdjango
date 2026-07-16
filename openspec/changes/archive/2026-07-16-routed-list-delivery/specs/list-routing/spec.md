# List Routing (delta)

## ADDED Requirements

### Requirement: Router declaration on `many=True` fields

`rx.model(Serializer(many=True), routing=...)` SHALL accept a Router: an
object providing `publish(instance)` — the group values a saved row
announces to — and `subscribe(channel)` — the group values a connection
listens on. Sugar forms SHALL be provided: a column string
(`routing='project_id'`) is a `ColumnRouter`, and the explicit broadcast
firehose is the framework-provided `BroadcastRouter` (the constant
function on both sides). `routing=None` SHALL raise at declaration time.
Omitted routing keeps the field a static list per `queryset-lists`.
Router values are opaque (tuples work); only the column sugar is
single-column.

#### Scenario: Column sugar

- **WHEN** a channel declares `tasks = rx.model(TaskSerializer(many=True), routing='project_id')`
- **THEN** rows announce to their `project_id` value and connections subscribe to the values their bind resolves

#### Scenario: routing=None rejected

- **WHEN** a class body evaluates `rx.model(TaskSerializer(many=True), routing=None)`
- **THEN** an error is raised at declaration time

### Requirement: `None` is never a group value

`None` SHALL be filtered from whatever `publish()` or `subscribe()`
returns: a row whose routing value is null is simply not announced; an
empty `publish()` set announces to no one; an empty `subscribe()` set
listens on nothing. Custom Routers inherit the rule with no code.

#### Scenario: Null routing column

- **WHEN** a row with `project_id = NULL` is saved under `routing='project_id'`
- **THEN** no dimension-group broadcast is sent for it

### Requirement: Lifecycle delivery through dimension groups

A saved creation SHALL broadcast the row's flat layer to the groups of
`publish(row)`; an update SHALL broadcast to `publish(old) ∪
publish(new)` — the old-side delivery is the stateless leave signal — and
a delete SHALL send the tombstone to `publish(row)`. The old values SHALL
come from a narrow pre-image read of only the Router's input columns,
inside the existing atomic block, and the read SHALL be skipped when
`update_fields` cannot affect those columns. The same dimension declared
by multiple fields or channels SHALL dedupe to one group set — one
broadcast per distinct dimension value in use, never per connection.

#### Scenario: Creation reaches watching connections

- **WHEN** a task with `project_id = 5` is created and a connection's bind subscribed to dimension value `5`
- **THEN** that connection receives the row's full layer without any prior relationship to the row

#### Scenario: Dimension move delivers to both sides

- **WHEN** a task moves from `project_id = 5` to `project_id = 7`
- **THEN** connections subscribed to `5` and connections subscribed to `7` both receive the update frame

#### Scenario: Pre-image read is gated

- **WHEN** a task is saved with `update_fields=['title']` under `routing='project_id'`
- **THEN** no pre-image read is issued and the update broadcasts to `publish(new)` only

### Requirement: Routing registers at import and is autodiscovered

Routing declarations SHALL register when the channel module is imported,
into plain imported code — no runtime registry, no shared discovery
state. The framework's `AppConfig.ready()` SHALL autodiscover each
installed app's `channels` module so registration happens in every
process type (web workers, task workers, management commands); a writer
process that skipped discovery would silently under-broadcast, so
discovery is framework-owned rather than per-app wiring.

#### Scenario: Management command broadcasts

- **WHEN** a management command saves a routed reactive row without importing any channel module itself
- **THEN** the dimension-group broadcast is still sent, because `AppConfig.ready()` imported the channel declarations

### Requirement: Subscriptions are bind-time snapshots with a rebind lever

`subscribe(channel)` SHALL run at bind; changes to the underlying
relation take effect on rebind. The channel SHALL expose a
`rebind(field)` lever that re-runs `subscribe()`, refreshes the field's
dimension-group joins, and re-snapshots the queryset (an authoritative
snapshot per `queryset-lists`).

#### Scenario: Membership relation change takes effect on rebind

- **WHEN** a connection's user gains access to a new project after bind and channel code calls `self.rebind('tasks')`
- **THEN** the connection joins the new dimension value's group and receives a fresh snapshot

### Requirement: Consumers may drop residual-failing creations only

A consumer MAY drop a relayed *creation* whose row fails the field's
frame-evaluable residual conditions, as a bandwidth optimization — safe
because a row the client never held needs no leave signal. Updates SHALL
never be dropped: a failing update frame is the leave signal.

#### Scenario: Failing update still relayed

- **WHEN** a member row's update arrives at the consumer with values failing the field's residual conditions
- **THEN** the frame is relayed to the client, which drops the row from the derived list
