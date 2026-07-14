# Memo Fields

## Purpose

`@memo('dep', ...)` turns a channel method into a derived, read-only reactive field recomputed when its named dependencies change (ADR-0006). On the wire and in the generated client a memo is indistinguishable from a plain rx field.

## Requirements

### Requirement: Declaration by decorator with named dependencies

A derived field SHALL be declared by decorating a channel method with `@memo('dep1', ...)`, where each dependency is the string name of another reactive field (rx or memo) on the same channel. At least one dependency is required; a non-string dependency SHALL raise `TypeError`.

#### Scenario: Memo over an rx field

- **WHEN** a class body declares `selected = rx[int](0)` and `@memo('selected') def fruit(self): return self.FRUITS[self.selected]`
- **THEN** `fruit` is a reactive field whose value tracks `selected`

### Requirement: Dependencies are validated at class creation

An unknown dependency name or a circular dependency chain SHALL raise `TypeError` when the channel class is created, before any connection exists.

#### Scenario: Unknown dependency

- **WHEN** a memo declares a dependency naming no field on the channel
- **THEN** class creation fails with a `TypeError` naming the memo and the unknown field

### Requirement: Initial value computed from defaults

Each memo's initial value SHALL be computed at class creation by evaluating its method against the channel's field defaults, in dependency order so memos may depend on other memos.

#### Scenario: Chained memo defaults

- **WHEN** `fruit` derives from `selected = rx[int](0)` and `first_letter` derives from `fruit`
- **THEN** before any connection, `fruit` defaults to `FRUITS[0]` and `first_letter` to its first character

### Requirement: Recompute on dependency change, emit on value change

When a reactive field changes value, every memo depending on it (directly or through other memos) SHALL be recomputed in dependency order. A memo whose recomputed value differs from its cached value SHALL be pushed to the client as an ordinary `rx` frame; an unchanged recompute SHALL emit nothing.

#### Scenario: One assignment fans out through the chain

- **WHEN** an action assigns `self.selected = 1` on the carousel memo channel
- **THEN** the client receives `rx` frames for `selected`, `fruit`, and `first_letter`

#### Scenario: Unchanged recompute is silent

- **WHEN** a dependency changes but the memo's method returns the same value as before
- **THEN** no `rx` frame is sent for the memo

### Requirement: Memo fields are read-only

Assigning to a memo field SHALL raise `AttributeError`; memo values only change through recomputation.

#### Scenario: Direct assignment rejected

- **WHEN** channel code assigns `self.fruit = 'mango'` where `fruit` is a memo
- **THEN** an `AttributeError` states the field is read-only and recomputed from its dependencies
