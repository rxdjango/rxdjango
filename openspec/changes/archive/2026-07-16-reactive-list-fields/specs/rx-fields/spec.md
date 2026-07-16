# Rx Fields — Delta

## MODIFIED Requirements

### Requirement: Typed scalar declaration

A scalar reactive field SHALL be declared as `rx[T](default)` where `T` is `int`, `str`, `float`, `bool`, or a union of one of those with `None`. Subscripting `rx` with any type that is neither a supported scalar form nor a supported list form (see *Typed list declaration*) SHALL raise `TypeError` at declaration time.

#### Scenario: Supported declaration

- **WHEN** a class body declares `counter = rx[int](0)`
- **THEN** the channel has a reactive integer field with default `0`

#### Scenario: Unsupported type

- **WHEN** a class body evaluates `rx[dict]`
- **THEN** a `TypeError` is raised naming the supported types

## ADDED Requirements

### Requirement: Typed list declaration

A list reactive field SHALL be declared as `rx[list[S]](default)` where `S` is any union drawn from `int`, `str`, `float`, `bool` (optionally including `None` for nullable elements). The None-union rule applies to the field itself: `rx[list[S] | None]` is optional with implicit default `None`. Bare `rx[list]` (no element type) and nested containers (`list[list[int]]`, `list[dict]`, …) SHALL raise `TypeError` at declaration time; the nested-container error SHALL state that element types must be scalars (ADR-0017: element immutability keeps every change an op).

#### Scenario: Homogeneous list

- **WHEN** a class body declares `items = rx[list[int]]([])`
- **THEN** the channel has a reactive list field with default `[]`

#### Scenario: Union element type

- **WHEN** a class body declares `mixed = rx[list[int | str]](['a', 1])`
- **THEN** the declaration is accepted

#### Scenario: Optional list

- **WHEN** a class body declares `items = rx[list[int] | None]()`
- **THEN** the field's default is `None`

#### Scenario: Nested container refused

- **WHEN** a class body evaluates `rx[list[list[int]]]`
- **THEN** a `TypeError` is raised explaining that list elements must be scalar types

#### Scenario: Bare list refused

- **WHEN** a class body evaluates `rx[list]`
- **THEN** a `TypeError` is raised requiring an element type

### Requirement: List defaults are element-validated

A list default SHALL be validated element-wise against the declared element union at declaration time; a default containing an element outside the union SHALL raise `TypeError` naming the offending element. Each connection SHALL start from its own copy of the default — mutating one connection's list never affects another connection or the class-level default.

#### Scenario: Wrong-typed default element

- **WHEN** a class body declares `items = rx[list[int]]([1, 'two'])`
- **THEN** a `TypeError` is raised at declaration time

#### Scenario: Connections do not share list state

- **WHEN** two clients connect and one triggers an action that appends to `items`
- **THEN** the other client's `items` is unchanged

### Requirement: In-place mutation emits delta operations

The list descriptor SHALL intercept every mutating `list` method — `append`, `insert`, `__setitem__`, `__delitem__`, `remove`, `pop`, `extend`, `clear`, `sort`, `reverse`, `__iadd__`, `__imul__`, and slice assignment — and enqueue the corresponding delta operation(s) per `wire-protocol`, or a whole-value replace for bulk mutators. Reassignment (`self.items = [...]`) SHALL enqueue a whole-value replace. After any server-side mutation, the client's list SHALL converge to the server's list.

#### Scenario: Append reaches the client incrementally

- **WHEN** an action body executes `self.items.append(4)` on `items = rx[list[int]]([1, 2, 3])`
- **THEN** the client receives a delta frame (not a full-value frame) and its `items` becomes `[1, 2, 3, 4]`

#### Scenario: Every mutator converges

- **WHEN** any single mutating list method runs server-side against a connected channel
- **THEN** the client's list equals the server's list afterwards

#### Scenario: Reassignment replaces

- **WHEN** an action body executes `self.items = [9, 8]`
- **THEN** the client receives a full-value `rx` frame with `v: [9, 8]` and no `o` key

### Requirement: List mutations are element-validated

Mutations that introduce values (`append`, `insert`, `__setitem__`, `extend`, …) SHALL validate each introduced value against the declared element union and raise `TypeError` on violation, leaving the list unchanged and sending nothing.

#### Scenario: Wrong-typed append

- **WHEN** channel code calls `self.items.append('x')` on `items = rx[list[int]]([])`
- **THEN** a `TypeError` is raised and no frame is sent

### Requirement: Mutating an optional list holding None follows Python semantics

When an optional list field's value is `None`, in-place mutation SHALL raise `AttributeError` exactly as calling a list method on `None` does in plain Python. Nothing is invented: assigning a list first is the way to begin mutating.

#### Scenario: Append on None

- **WHEN** channel code calls `self.items.append(1)` while `items = rx[list[int] | None]()` still holds `None`
- **THEN** an `AttributeError` is raised and no frame is sent
