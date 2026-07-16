# React Client — Delta

## ADDED Requirements

### Requirement: List delta frames are applied positionally in arrival order

For a list field, an `rx` frame carrying `o` SHALL be applied as the positional operation it names (`"i"` insert, `"s"` set, `"d"` delete per `wire-protocol`), in arrival order; a frame without `o` SHALL replace the whole value. Each applied frame SHALL produce a new array identity and publish a new state version, so React re-renders. This op application is the base list contract (ADR-0017): the state machine is the one later fed locally by the queryset tier's derivation engine, which never receives ops from the wire.

#### Scenario: Streamed appends grow the array

- **WHEN** the server emits three consecutive `{"o": "i"}` frames for `items`
- **THEN** the component re-renders three times and `channel.items` has the three values appended in order

#### Scenario: Mixed burst converges

- **WHEN** insert, set, and delete frames for one field arrive back-to-back
- **THEN** after processing, `channel.items` equals the server's list

#### Scenario: Replace resets the array

- **WHEN** a plain `rx` frame (no `o`) arrives for `items` after several ops
- **THEN** `channel.items` is exactly the frame's `v`
