# Frontend Codegen (delta)

## ADDED Requirements

### Requirement: `many=True` anchor fields generate array state types

A channel field declared with a `many=True` serializer SHALL generate a channel property typed `T[] | null` (where `T` is the anchor's generated interface), initialized to `null`. Elements are never typed as unloaded stubs — snapshot anchors arrive fully loaded — while nested relations inside `T` keep their existing stub unions. The `_modelFields` metadata SHALL mark the field as list-valued so the runtime routes it through membership derivation.

#### Scenario: List anchor property

- **WHEN** a channel declares `tasks = rx.model(TaskSerializer(many=True))`
- **THEN** the generated channel declares `tasks: Task[] | null = null`
- **AND** `_modelFields.tasks` is marked as a list anchor

#### Scenario: Nested relations inside elements still stub

- **WHEN** `TaskSerializer` nests `ProjectSerializer`
- **THEN** the generated `Task.project` remains `Project | Unloaded` (plus `| null` when `allow_null`)
