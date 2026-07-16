# React Client

## Purpose

The `@rxdjango/react` runtime binds a generated channel class to React. Components call `useChannel` once and read state directly off the channel instance; the framework handles connection, subscriptions, and re-rendering. Frame handling follows `wire-protocol`; nested-state rebuilding follows `model-state`.

## Requirements

### Requirement: useChannel returns a stable, subscribed channel

`useChannel(ChannelClass)` SHALL construct the channel once per component instance and subscribe it through `useSyncExternalStore`, re-rendering the component every time the channel publishes a new state version. The same instance is returned on every render.

#### Scenario: Counter component tracks pushes

- **WHEN** a component renders `const channel = useChannel(CounterChannel)` and the server pushes a `counter` update
- **THEN** the component re-renders and `channel.counter` reads the new value

### Requirement: Lazy connection on first subscription

The channel SHALL open its WebSocket on the first React subscription, joining the generated `baseURL` and `endpoint`. No connection is made by merely constructing the instance without a URL.

#### Scenario: Mounting connects

- **WHEN** a component using the channel mounts
- **THEN** the client connects to `<baseURL><endpoint>` and processes the ready frame

### Requirement: State is read directly off the instance

Server-pushed `rx` frames SHALL update the channel instance's fields in place (rebuilding nested model fields per `model-state`), and each processed frame publishes a new state version to subscribers.

#### Scenario: Field read in JSX

- **WHEN** a component renders `channel.counter` after an update frame arrived
- **THEN** the rendered value is the frame's `v`

### Requirement: Action wrappers return promises

Calling a generated action wrapper SHALL send the `ac` request and return a promise that resolves with the response's `r` on success and rejects with an `Error` carrying the numeric `code` from the response's `e` on failure. Requests sent before the socket opens are queued and flushed on open.

#### Scenario: Rejection carries the code

- **WHEN** a client calls a gated action without authorization
- **THEN** the returned promise rejects with an error whose `code` is `403`

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
