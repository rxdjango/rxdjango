# Model State — Delta: layered-state-delivery

## MODIFIED Requirements

### Requirement: Serializer tree is compiled at class creation

The framework SHALL walk the serializer tree once when the channel class is created, deriving the flat per-layer serializers, each layer's `_type` (the serializer's dotted module path), the relation map between layers, and the layered query plan: the breadth-first layer order and, for each layer, which relation fields of the previous layer's output feed each instance type's pk set. Serializer-shape errors therefore surface at import time, not per connection or per message. Only the pk sets are runtime data.

#### Scenario: Nested serializer compiled once

- **WHEN** `UserSerializer` embeds `CompanySerializer` and a channel declares `user = rx.model(UserSerializer())`
- **THEN** class creation builds layers for both serializer types and records that `user.company` holds a `CompanySerializer` instance reference

#### Scenario: Query plan is a class-creation artifact

- **WHEN** a channel declares `project = rx.model(ProjectSerializer())` whose serializer nests tasks, and tasks nest assignees and comments
- **THEN** the compiled plan orders layers breadth-first (project, then task, then user and comment) with the relation edges feeding each layer's pk sets, before any connection exists

### Requirement: Assignment sends flat, type-tagged layers

Assigning a model instance (or queryset, for list fields) to an `rx.model` field SHALL execute the compiled query plan breadth-first and send one `rx` frame per completed layer, in layer order, so an instance's frame is always preceded by the frame of every parent referencing it. Each frame's `v` is a flat array of layer dicts carrying serializer output plus `_type`; nested serializer fields are replaced by primary-key references; rows of a reactive model additionally carry `_v`. Frames for the same field are merge frames: the client merges them into the field's accumulated flat state per instance, reconciled by `_v` watermark, rather than replacing the field value wholesale. Assigning a field again before a prior assignment's layers have been delivered SHALL supersede the prior walk: no further frames from the superseded assignment are sent.

#### Scenario: Task with its project travels as two frames

- **WHEN** `on_connect` assigns a `Task` (whose serializer nests `ProjectSerializer`) to the `task` field
- **THEN** the client receives an `rx` frame for `task` whose `v` holds the flat task dict, its `project` key holding the project's `id`
- **AND** a subsequent `rx` frame for `task` whose `v` holds the flat project dict
- **AND** each layer dict carries its `_type` dotted serializer path

#### Scenario: Anchor paints before the deepest branch is fetched

- **WHEN** a project with many tasks and comments is assigned
- **THEN** the anchor project frame is enqueued as soon as its layer completes, before comment rows are queried

#### Scenario: Reassignment supersedes a pending walk

- **WHEN** `on_connect` assigns task `a` to the `task` field and then assigns task `b` before `a`'s layers have been delivered
- **THEN** the client receives only `b`'s layer frames for `task`; no frame from `a`'s walk is sent

### Requirement: Clearing a model field

Assigning `None` to an `rx.model` field SHALL send an `rx` frame with `v: null`; the client resets its rebuild state for the field and exposes `null`. Clearing SHALL supersede any pending walk for the field: no layer frame from a prior assignment is sent after the `v: null` frame.

#### Scenario: Field cleared

- **WHEN** channel code assigns `self.task = None`
- **THEN** the client's `channel.task` becomes `null` and previously held layers are forgotten

#### Scenario: Clearing mid-delivery sends no stale layers

- **WHEN** a task is assigned and the field is cleared before the assignment's layers have been delivered
- **THEN** the client receives no layer frame for the field after the `v: null` frame

### Requirement: The client rebuilds the nested shape

Using the relation map generated at compile time, the client SHALL splice flat layers back into the nested structure declared by the serializer tree, keyed by `_type:id`. A relation reference whose instance has not arrived resolves to a typed stub `{ id, _loaded: false }` carrying the referenced pk; a relation whose serialized value is `null` resolves to `null`. When the referenced instance arrives, the stub is replaced by the loaded instance.

#### Scenario: Nested read on the client

- **WHEN** the flat task frame and the flat project frame have both arrived
- **THEN** `channel.task.project.name` reads the project's field through the rebuilt nesting

#### Scenario: Unarrived child reads as a stub

- **WHEN** the task frame has arrived but the project frame has not
- **THEN** `channel.task.project` is `{ id: <project pk>, _loaded: false }`

#### Scenario: Explicit null FK stays null

- **WHEN** a task's serialized `project` value is `null`
- **THEN** `channel.task.project` is `null`, not a stub

## ADDED Requirements

### Requirement: Layered walk queries are batched per type and run off the event loop

Each layer SHALL be resolved with one `pk__in` query per instance type, the pk set collected and deduplicated from the previous layer's serialized relation fields, so query count is O(edges in the serializer tree) and independent of row counts. To-one edges SHALL NOT be folded into the parent layer's query via `select_related` — every edge resolves as a pk set. Layer queries SHALL run off the event loop; the consumer's loop is handed a completed layer, never a per-row callback.

#### Scenario: Shared child fetched once

- **WHEN** two tasks in a layer reference the same assignee pk
- **THEN** the user layer's `pk__in` query lists that pk once and the row is fetched once

#### Scenario: Query count independent of row count

- **WHEN** a project with 50 tasks, each with an assignee and comments, is assigned
- **THEN** the walk issues one query for the project, one for tasks, one for users, and one for comments — regardless of the 50

### Requirement: Stubs are client-constructed and replaced unconditionally

Stubs SHALL be materialized by the client from the pk references the parent layer already carries; the server never sends a stub over the wire. Stubs carry no `_v`: any real instance replaces a stub unconditionally, and version watermarks apply only between real instances. Replacing a stub is a reference change that propagates up the parents map like any instance update.

#### Scenario: Real instance replaces stub regardless of version

- **WHEN** a stub occupies a relation slot and a real instance with any `_v` arrives for that `_type:id`
- **THEN** the stub is replaced by the instance
- **AND** ancestors of the slot get new references

#### Scenario: Stub identity is stable while unloaded

- **WHEN** a parent is re-read twice while its child has not arrived
- **THEN** both reads yield the same stub object reference
