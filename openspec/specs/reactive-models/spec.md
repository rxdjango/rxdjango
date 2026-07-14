# Reactive Models

## Purpose

A Django model inheriting `ReactiveModel` broadcasts every committed write to the clients currently holding that row through an `rx.model` field, with no code in the channel (ADR-0013). Consistency across the initial snapshot and the event stream is kept by per-row versions reconciled on the client (ADR-0014).

## Requirements

### Requirement: Opt-in via the ReactiveModel base class

Reactivity SHALL be opted into by inheriting `ReactiveModel`, which contributes a database-owned `_v` bigint version column. Broadcasts fire only through instance `save()` and `delete()`; bulk queryset operations and cascade deletes are not detected.

#### Scenario: Reactive project model

- **WHEN** `Project` inherits `ReactiveModel` and a row is saved
- **THEN** the row's `_v` increments and subscribed clients receive the change

### Requirement: Atomic versioned save, broadcast on commit

`save()` SHALL run the write and the version bump inside one atomic block, so the broadcast version provably belongs to that write, and SHALL defer the broadcast to transaction commit — immediate in autocommit, on the caller's commit inside a transaction. The broadcast payload is the row's flat serialized layer carrying the new `_v`.

#### Scenario: Change from outside the channel context

- **WHEN** a background thread loads a `Project`, changes its name, and calls `save()`
- **THEN** every client whose channel relayed that project receives an `rx` frame with the updated layer, without any action or refresh

### Requirement: Versioned delete events

`delete()` SHALL broadcast, on commit, a delete event `{"_type": ..., "_del": <pk>, "_v": <final version + 1>}`. Because nothing can write the row after deletion, this version always wins over any in-flight snapshot of the row.

#### Scenario: Row deleted while a snapshot is in flight

- **WHEN** a reactive row is deleted and a client later receives a stale snapshot of it
- **THEN** the client keeps the row deleted

### Requirement: Broadcasts reach exactly the clients holding the row

A broadcast group SHALL exist per (serializer type, row id); a connection joins the group of every reactive instance it relays and leaves it when the row is deleted or the connection closes. A row change is delivered once per serializer shape registered for the model, only to subscribed connections, and is routed on arrival to the `rx.model` field that holds the row.

#### Scenario: Only holders are notified

- **WHEN** two clients are connected and only one has relayed project 1
- **THEN** saving project 1 pushes a frame to that client alone

### Requirement: Client version reconciliation

The client SHALL track a per-`_type:id` version watermark and apply a versioned layer only if its `_v` exceeds the watermark, discarding stale layers. Delete events leave a tombstone whose watermark persists for the connection. Layers without `_v` come from non-reactive models and are always applied.

#### Scenario: Late snapshot loses to a newer event

- **WHEN** an event with `_v: 5` for a row arrives before an initial-snapshot layer with `_v: 4` for the same row
- **THEN** the snapshot layer is discarded and the client keeps the event's data
