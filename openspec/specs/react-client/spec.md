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
