# Wire Protocol

## Purpose

Defines the WebSocket message envelope spoken between a `ContextChannel` server and a generated TypeScript client (ADR-0002). Both ends are independent codebases, so the frame shapes and key names specified here are contract: every message is a JSON object discriminated by a single `t` key. Frame types carrying model state are further specified in `model-state` and `reactive-models`.

## Requirements

### Requirement: JSON envelope with a `t` discriminator

Every WebSocket message in either direction SHALL be a JSON object whose `t` key identifies the frame type. The server sends `ready`, `rx`, and `ac` frames; the client sends `ac` frames.

#### Scenario: A full increment round-trip

- **WHEN** a client connects to a counter channel and calls the `increment` action
- **THEN** the complete trace is four frames, each a JSON object with a `t` key: a server `ready` frame, a client `ac` request, a server `ac` response, and a server `rx` update

### Requirement: Ready frame opens the conversation

After accepting a connection and running the channel's `on_connect` hook, the server SHALL send `{"t": "ready", "protocol": "<semver>"}` before any other frame. The current protocol version is `0.1.0`.

#### Scenario: Ready precedes initial state

- **WHEN** a channel assigns reactive state during `on_connect`
- **THEN** the client first receives `{"t": "ready", "protocol": "0.1.0"}`
- **AND** the `rx` frames carrying the assigned state follow the ready frame

### Requirement: `rx` frames carry full replacement values

A reactive update SHALL be sent as `{"t": "rx", "f": "<field>", "v": <value>}`, where `f` names the channel field and `v` is the field's full new value. No partial-operation key exists; the client replaces the field value with `v`. (For `rx.model` fields, `v` is an array of flat layers — see `model-state`.)

#### Scenario: Scalar field update

- **WHEN** an action body executes `self.counter += 1` on a channel with `counter = rx[int](0)`
- **THEN** the server sends `{"t": "rx", "f": "counter", "v": 1}`

### Requirement: `ac` request and response shapes

A client action call SHALL be sent as `{"t": "ac", "a": "<method>", "id": "<call id>", "p": [<positional params>]}`. The server SHALL respond with a frame carrying the same `id`: on success `{"t": "ac", "id": ..., "r": <return value>, "e": 0}`; on failure `{"t": "ac", "id": ..., "e": [<code>, "<message>"]}` with no `r` key.

#### Scenario: Successful call correlates by id

- **WHEN** the client sends `{"t": "ac", "a": "increment", "id": "1", "p": []}`
- **THEN** the server responds `{"t": "ac", "id": "1", "r": null, "e": 0}` for an action returning `None`

#### Scenario: Failed call carries code and message

- **WHEN** an action is rejected or raises
- **THEN** the response's `e` is a two-element array `[code, message]` — 403 for a forbidden call, the exception's `code` attribute or 500 for an unhandled error

### Requirement: Malformed action requests are answered with 400

When an `ac` request is missing `id`, `a`, or `p`, or `p` is not an array, the server SHALL respond with `{"t": "ac", "id": ..., "e": [400, "<message>"]}` and SHALL NOT execute any action. A request missing its `id` gets the error frame with `id: null` — uncorrelatable by design, sent so a misbehaving client is diagnosable rather than silently ignored.

#### Scenario: Non-array params

- **WHEN** the client sends an `ac` frame whose `p` is not an array
- **THEN** the server responds with an error frame whose `e` code is 400
- **AND** no action method runs

#### Scenario: Missing id still gets a diagnostic error

- **WHEN** the client sends an `ac` frame with `a` and `p` but no `id`
- **THEN** the server responds with an error frame whose `e` code is 400 and whose `id` is `null`
- **AND** no action method runs

### Requirement: Invalid frames are rejected

The server SHALL NOT process a client message that is not valid JSON or whose `t` is missing or unknown. Malformed JSON closes the connection; a missing or unrecognized `t` raises a server-side error and the frame is discarded.

#### Scenario: Unknown discriminator

- **WHEN** the client sends `{"t": "bogus"}`
- **THEN** no channel method executes and no success response is sent

### Requirement: Reactive updates flush after the action response

`rx` updates produced while an action body runs SHALL be delivered after the `ac` response frame for that action.

#### Scenario: Increment ordering

- **WHEN** the `increment` action mutates `counter` and returns
- **THEN** the server sends the `ac` success frame first
- **AND** the `{"t": "rx", "f": "counter", ...}` frame after it
