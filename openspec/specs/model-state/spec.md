# Model State

## Purpose

`rx.model(serializer)` declares nested Django model state on a channel using the DRF serializers the developer already writes (ADR-0010). The serializer tree is introspected once at class creation (ADR-0015); state travels as flat, `_type`-tagged layers and is rebuilt into the nested shape on the client (ADR-0012). Provided by the `rxdjango_model` backend package plugging into the dependency-light core (ADR-0011).

## Requirements

### Requirement: Declaration with a DRF serializer instance

A nested-state field SHALL be declared as `rx.model(serializer)` where `serializer` is a DRF serializer instance; a `many=True` (list) serializer declares a list-valued field. Passing anything that is not a DRF serializer instance SHALL raise `TypeError`.

#### Scenario: Single-instance field

- **WHEN** a class body declares `task = rx.model(TaskSerializer())`
- **THEN** the channel has a nested-state field defaulting to `None` whose shape is the serializer's output

#### Scenario: Non-serializer rejected

- **WHEN** a class body evaluates `rx.model(Task)` with a model class instead of a serializer instance
- **THEN** a `TypeError` is raised at declaration time

### Requirement: Serializer tree is compiled at class creation

The framework SHALL walk the serializer tree once when the channel class is created, deriving the flat per-layer serializers, each layer's `_type` (the serializer's dotted module path), and the relation map between layers. Serializer-shape errors therefore surface at import time, not per connection or per message.

#### Scenario: Nested serializer compiled once

- **WHEN** `UserSerializer` embeds `CompanySerializer` and a channel declares `user = rx.model(UserSerializer())`
- **THEN** class creation builds layers for both serializer types and records that `user.company` holds a `CompanySerializer` instance reference

### Requirement: Assignment sends flat, type-tagged layers

Assigning a model instance (or queryset, for list fields) to an `rx.model` field SHALL send a single `rx` frame whose `v` is a flat array of layer dicts. Each dict carries its serializer output plus `_type`; nested serializer fields are replaced by primary-key references; rows of a reactive model additionally carry `_v`. Anchor instances precede the child layers they reference.

#### Scenario: Task with its project travels as two flat dicts

- **WHEN** `on_connect` assigns a `Task` (whose serializer nests `ProjectSerializer`) to the `task` field
- **THEN** the client receives one `rx` frame for `task` whose `v` is a two-element array
- **AND** the task layer's `project` key holds the project layer's `id`
- **AND** each layer carries its `_type` dotted serializer path

### Requirement: The client rebuilds the nested shape

Using the relation map generated at compile time, the client SHALL splice flat layers back into the nested structure declared by the serializer tree, keyed by `_type:id`. A reference whose instance has not arrived resolves to `null`.

#### Scenario: Nested read on the client

- **WHEN** the flat `[Task, Project]` frame arrives
- **THEN** `channel.task.project.name` reads the project's field through the rebuilt nesting

### Requirement: Rebuilt state is reference-stable

The client SHALL cache built instances and invalidate only along the changed path, so an update allocates new objects only where data changed: untouched instances keep their references between reads, and an instance referenced from two relations is the same object in both.

#### Scenario: Unrelated sibling keeps identity

- **WHEN** one child instance is updated while a sibling instance is untouched
- **THEN** the rebuilt state's sibling object is the same reference as before the update

### Requirement: Clearing a model field

Assigning `None` to an `rx.model` field SHALL send an `rx` frame with `v: null`; the client resets its rebuild state for the field and exposes `null`.

#### Scenario: Field cleared

- **WHEN** channel code assigns `self.task = None`
- **THEN** the client's `channel.task` becomes `null` and previously held layers are forgotten
