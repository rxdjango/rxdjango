# Wire Protocol — Delta

## MODIFIED Requirements

### Requirement: `rx` frames carry full replacement values

A reactive update SHALL be sent as `{"t": "rx", "f": "<field>", "v": <value>}`, where `f` names the channel field and `v` is the field's full new value; the client replaces the field value with `v`. A frame MAY additionally carry the `o` key, in which case it is a list delta operation (see *List delta operations on the `o` slot*) and `v` is the operation's operand rather than a full value. A frame without `o` is always a full replacement. (For `rx.model` fields, `v` is an array of flat layers — see `model-state`.)

#### Scenario: Scalar field update

- **WHEN** an action body executes `self.counter += 1` on a channel with `counter = rx[int](0)`
- **THEN** the server sends `{"t": "rx", "f": "counter", "v": 1}`

#### Scenario: List reassignment is a plain frame

- **WHEN** an action body executes `self.items = [1, 2]` on a list field
- **THEN** the server sends `{"t": "rx", "f": "items", "v": [1, 2]}` with no `o` key

### Requirement: Ready frame opens the conversation

After accepting a connection and running the channel's `on_connect` hook, the server SHALL send `{"t": "ready", "protocol": "<semver>"}` before any other frame. The current protocol version is `0.2.0` (the `o` slot's first population is an additive, minor-version change).

#### Scenario: Ready precedes initial state

- **WHEN** a channel assigns reactive state during `on_connect`
- **THEN** the client first receives `{"t": "ready", "protocol": "0.2.0"}`
- **AND** the `rx` frames carrying the assigned state follow the ready frame

## ADDED Requirements

### Requirement: List delta operations on the `o` slot

An incremental list update SHALL be sent as `{"t": "rx", "f": "<field>", "o": "<op>", "v": <operand>}` with exactly three operations, all positional (ADR-0017):

- `"i"` — insert: `v` is `[index, value]`; the value is inserted at the index.
- `"s"` — set: `v` is `[index, value]`; the element at the index is replaced.
- `"d"` — delete: `v` is the index; the element at the index is removed.

Operations carry no sequence numbers: the client SHALL apply them in arrival order (single producer over a FIFO socket makes op order application order by construction). There is no move operation; a reorder is delete + insert.

#### Scenario: Append

- **WHEN** an action body executes `self.items.append(4)` on `items = rx[list[int]]([1, 2, 3])`
- **THEN** the server sends `{"t": "rx", "f": "items", "o": "i", "v": [3, 4]}`

#### Scenario: Set by index

- **WHEN** an action body executes `self.items[0] = 9`
- **THEN** the server sends `{"t": "rx", "f": "items", "o": "s", "v": [0, 9]}`

#### Scenario: Delete by index

- **WHEN** an action body executes `del self.items[1]`
- **THEN** the server sends `{"t": "rx", "f": "items", "o": "d", "v": 1}`

#### Scenario: Burst applies in order

- **WHEN** an action performs an interleaved sequence of appends, inserts, sets, and deletes
- **THEN** the frames arrive in mutation order and the client's list converges to the server's list

### Requirement: `o` is exclusive to list fields

The server SHALL only emit `o`-carrying frames for fields declared as `rx[list[S]]` variants. A client receiving an `o` frame for a non-list field SHALL discard it (unknown-operation tolerance mirrors the envelope's forward-compatibility posture).

#### Scenario: Scalar fields never carry `o`

- **WHEN** any scalar or model field updates
- **THEN** the emitted `rx` frames have no `o` key
