# Context Channels

## Purpose

The `ContextChannel` class is the framework's declaration surface (ADR-0003): a developer declares reactive state and actions on a class body, mounts the class on a WebSocket URL, and the framework handles the connection lifecycle. This spec covers declaration, the per-connection lifecycle, and ASGI mounting; the field kinds themselves are specified in `rx-fields`, `memo-fields`, and `model-state`.

## Requirements

### Requirement: Channels are declared as ContextChannel subclasses

A channel SHALL be declared by subclassing `rxdjango.ContextChannel` and assigning reactive field descriptors and `@action` methods on the class body.

#### Scenario: Minimal counter channel

- **WHEN** a developer declares `class CounterChannel(ContextChannel)` with `counter = rx[int](0)` and an `@action` method
- **THEN** the class is a complete, connectable channel with no hand-written consumer code

### Requirement: The reactive field set is fixed at class creation

The framework SHALL collect a channel's reactive fields (any `rx`, `@memo`, or `rx.model` descriptor on the class body) once, when the class is created. Only collected fields participate in reactive delivery; validation errors in any field declaration surface at import time.

#### Scenario: Fields are discovered from the class body

- **WHEN** a channel class body declares `selected = rx[int](0)` and a `@memo` field
- **THEN** both are registered as reactive fields at class creation
- **AND** dependency validation between them runs immediately, before any connection exists

### Requirement: Abstract channels

A channel class whose `Meta` declares `abstract = True` SHALL be exempt from reactive field collection and validation, serving as a base class for concrete channels.

#### Scenario: Base class opts out of processing

- **WHEN** a channel class declares `class Meta: abstract = True`
- **THEN** no field collection, memo validation, or action gating configuration runs for that class

### Requirement: One channel instance per connection

The framework SHALL instantiate a fresh channel object for every accepted WebSocket connection, so reactive state is per-client.

#### Scenario: Two clients count independently

- **WHEN** two clients connect to the same counter channel and one calls `increment`
- **THEN** only the calling client's `counter` changes

### Requirement: Connection lifecycle hooks

The framework SHALL call `await channel.on_connect(**kwargs)` after accepting a connection, passing the URL route's captured parameters as keyword arguments, and SHALL call `await channel.on_disconnect()` when the connection closes. State assigned during `on_connect` is delivered to the client after the ready frame.

#### Scenario: URL parameters reach on_connect

- **WHEN** a channel is mounted at a path with a captured parameter and a client connects
- **THEN** `on_connect` receives that parameter as a keyword argument before any frame is sent

#### Scenario: Initial state assigned in on_connect

- **WHEN** `on_connect` assigns a reactive field
- **THEN** the client receives the ready frame followed by the `rx` frame for that assignment

### Requirement: ASGI mounting via as_asgi

`ContextChannel.as_asgi()` SHALL return an ASGI application suitable for mounting in a Channels `URLRouter`, requiring no hand-written consumer.

#### Scenario: Mounting a channel on a WebSocket route

- **WHEN** a route list contains `path('ws/counter/', CounterChannel.as_asgi())` under the ASGI `websocket` router
- **THEN** WebSocket connections to `/ws/counter/` are served by the channel
