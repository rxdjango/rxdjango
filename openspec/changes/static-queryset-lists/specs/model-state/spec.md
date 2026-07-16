# Model State (delta)

## MODIFIED Requirements

### Requirement: Declaration with a DRF serializer instance

A nested-state field SHALL be declared as `rx.model(serializer)` where `serializer` is a DRF serializer instance; a `many=True` (list) serializer declares a list-valued field whose anchor is the child serializer's type. Class creation SHALL compile a `many=True` declaration exactly like its single-instance counterpart (the serializer tree is unwrapped from the list wrapper before disassembly). Passing anything that is not a DRF serializer instance SHALL raise `TypeError`.

#### Scenario: Single-instance field

- **WHEN** a class body declares `task = rx.model(TaskSerializer())`
- **THEN** the channel has a nested-state field defaulting to `None` whose shape is the serializer's output

#### Scenario: List field compiles at class creation

- **WHEN** a class body declares `tasks = rx.model(TaskSerializer(many=True))`
- **THEN** class creation succeeds, deriving the same layers and relation map as `TaskSerializer()` would, with the field marked list-valued

#### Scenario: Non-serializer rejected

- **WHEN** a class body evaluates `rx.model(Task)` with a model class instead of a serializer instance
- **THEN** a `TypeError` is raised at declaration time

### Requirement: Assignment sends flat, type-tagged layers

Assigning a model instance (or queryset, for list fields) to an `rx.model` field SHALL execute the compiled query plan breadth-first and send one `rx` frame per completed layer, in layer order, so an instance's frame is always preceded by the frame of every parent referencing it. For a list field, the anchor layer SHALL be the queryset's full row set delivered in a single frame — the snapshot — carrying the bind descriptor per `wire-protocol`; an empty queryset sends an anchor frame with an empty layer array. Each frame's `v` is a flat array of layer dicts carrying serializer output plus `_type`; nested serializer fields are replaced by primary-key references; rows of a reactive model additionally carry `_v`. Frames for the same field are merge frames: the client merges them into the field's accumulated flat state per instance, reconciled by `_v` watermark, rather than replacing the field value wholesale. Assigning a field again before a prior assignment's layers have been delivered SHALL supersede the prior walk: no further frames from the superseded assignment are sent.

#### Scenario: Task with its project travels as two frames

- **WHEN** `on_connect` assigns a `Task` (whose serializer nests `ProjectSerializer`) to the `task` field
- **THEN** the client receives an `rx` frame for `task` whose `v` holds the flat task dict, its `project` key holding the project's `id`
- **AND** a subsequent `rx` frame for `task` whose `v` holds the flat project dict
- **AND** each layer dict carries its `_type` dotted serializer path

#### Scenario: Queryset snapshot anchors in one frame

- **WHEN** `on_connect` assigns a queryset of three tasks to a `many=True` field
- **THEN** the first frame for the field carries all three flat task dicts in `v` together with the bind descriptor
- **AND** child layers (projects, assignees) follow as ordinary merge frames

#### Scenario: Anchor paints before the deepest branch is fetched

- **WHEN** a project with many tasks and comments is assigned
- **THEN** the anchor project frame is enqueued as soon as its layer completes, before comment rows are queried

#### Scenario: Reassignment supersedes a pending walk

- **WHEN** `on_connect` assigns task `a` to the `task` field and then assigns task `b` before `a`'s layers have been delivered
- **THEN** the client receives only `b`'s layer frames for `task`; no frame from `a`'s walk is sent
