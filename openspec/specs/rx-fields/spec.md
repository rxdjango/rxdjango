# Rx Fields

## Purpose

`rx[T](default)` declares a typed scalar reactive field on a channel class body (ADR-0004). Assigning the field on a connected channel pushes the new value to the client. Declarations are validated at import time, assignments at runtime.

## Requirements

### Requirement: Typed scalar declaration

A scalar reactive field SHALL be declared as `rx[T](default)` where `T` is `int`, `str`, `float`, `bool`, or a union of one of those with `None`. Subscripting `rx` with any other type SHALL raise `TypeError` at declaration time.

#### Scenario: Supported declaration

- **WHEN** a class body declares `counter = rx[int](0)`
- **THEN** the channel has a reactive integer field with default `0`

#### Scenario: Unsupported type

- **WHEN** a class body evaluates `rx[list]`
- **THEN** a `TypeError` is raised naming the supported types

### Requirement: Default value rules

A default SHALL be required unless the field's type union includes `None`, in which case the implicit default is `None`. An explicit `None` default SHALL be rejected unless `None` is in the union. A default of a type outside the union SHALL be rejected. All three violations raise `TypeError` at declaration time.

#### Scenario: Missing default on a non-optional field

- **WHEN** a class body declares `name = rx[str]()`
- **THEN** a `TypeError` instructs declaring `rx[str | None]` for an optional field

#### Scenario: Optional field without default

- **WHEN** a class body declares `name = rx[str | None]()`
- **THEN** the field's default is `None`

### Requirement: Runtime assignment validation

Assigning a value whose type is outside the field's declared union SHALL raise `TypeError` naming the field and the allowed types. The previous value is retained.

#### Scenario: Wrong-typed assignment

- **WHEN** channel code assigns `self.counter = 'one'` on `counter = rx[int](0)`
- **THEN** a `TypeError` is raised and no update is sent

### Requirement: Assignment pushes to the client

Assigning a valid value to an rx field on a channel bound to a live connection SHALL enqueue an `rx` frame carrying the field name and new value, delivered per the ordering rules in `wire-protocol`.

#### Scenario: Increment reaches the client

- **WHEN** an action body executes `self.counter += 1`
- **THEN** the client receives `{"t": "rx", "f": "counter", "v": 1}` after the action response

### Requirement: Class-body value semantics

Within the class body, an `rx` descriptor whose default is an `int`, `str`, or `float` SHALL behave as an instance of that type carrying the default value, so downstream declarations can compute from it.

#### Scenario: Deriving one default from another

- **WHEN** a class body declares `selected = rx[int](0)`, `fruit = rx[str](FRUITS[selected])`, and `first_letter = rx[str](fruit[0])`
- **THEN** `fruit` defaults to `FRUITS[0]` and `first_letter` to its first character

### Requirement: rx[bool] is compared by equality, not identity

Because `bool` cannot be subclassed, an `rx[bool]` descriptor is NOT the `True`/`False` singleton (ADR-0008). Code comparing an rx bool in a class body SHALL use equality; identity comparison against `True` yields `False`.

#### Scenario: Identity check fails by design

- **WHEN** a class body declares `selected = rx[bool](True)` and evaluates `selected is True`
- **THEN** the expression is `False`, while `selected == True` is `True`
