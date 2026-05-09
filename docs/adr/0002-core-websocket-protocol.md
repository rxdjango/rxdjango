# 0002. Define the core WebSocket protocol envelope

- **Date:** 2026-05-09
- **Deciders:** Luis Fagundes

## Context

RxDjango's reactive model machinery relies on a single WebSocket carrying three
distinct kinds of traffic: a one-shot handshake the server sends on connect,
streaming field updates the server pushes as state changes, and request/response
action calls initiated by the client. The original (v0.0.x) implementation grew
its wire format ad hoc; the rebuild needs a stable, minimal envelope that:

- Is small on the wire — RxDjango can emit many field-level updates per second,
  so verbose JSON keys are a real cost.
- Discriminates message kinds with a single field, so both ends can dispatch
  before parsing the rest of the payload.
- Reserves room for protocol evolution via an explicit version number sent
  before any other traffic flows.
- Keeps client- and server-initiated action calls on the same shape, so the
  request and its response correlate by id without a separate channel.
- Carves out a namespace for framework-internal actions that user code cannot
  shadow.

This ADR locks down the envelope. Field-level diff semantics, action dispatch,
and serializer mapping are deferred to subsequent ADRs and reference this
envelope as their substrate.

## Decision

Every WebSocket message is a JSON object with a `t` (type) discriminator whose
value is one of `ready`, `rx`, or `ac`. The remaining keys are determined by
`t`:

- **`t: "ready"`** — sent once by the server immediately after the connection
  opens. Carries `protocol`: a string with the protocol's semantic version.
- **`t: "rx"`** — a reactive field update pushed by the server. Carries `f`
  (field name, string), and at least one of `v` (new value) and `o` (operation,
  e.g. `"append"`, `"pop"`). With no `o`, `v` replaces the field. With `o`,
  `v` is the operand when the operation needs one (`append` requires `v`;
  `pop` does not).
- **`t: "ac"`** — an action call. Client→server carries `a` (action method
  name, string), `id` (client-generated uid, string), and `p` (parameters).
  Server→client response carries the same `id` and `r` (result). Action names
  beginning with `_` are reserved for framework-internal use and MUST NOT be
  registered by application code.

Keys are deliberately one or two characters; this is a wire format, not a
developer-authored DSL.

## Consequences

### Positive
- Single discriminator (`t`) lets both ends route messages without parsing the
  rest of the payload first.
- Short keys keep per-message overhead low for the high-volume `rx` stream.
- Versioning the protocol in `ready` lets clients refuse or adapt to a server
  speaking a different major version before any other traffic is exchanged.
- Symmetric `ac` shape with a client-supplied `id` makes request/response
  correlation trivial and avoids a second control channel.
- Reserved `_` action prefix keeps a future internal RPC namespace open
  without risking collision with user code.

### Negative / Trade-offs
- Single-letter keys hurt readability when inspecting traffic by eye; tooling
  (devtools formatter, logging middleware) will need to compensate.
- A flat envelope without a separate `meta`/`data` split means future
  additions either lengthen the top-level key set or force a versioned
  reshuffle via `ready.protocol`.
- `rx` allowing `v`, `o`, or both pushes validation onto each operation
  handler rather than the parser; misuse is caught later than it could be
  with stricter shapes.

### Neutral
- JSON, not a binary format. Adequate for the expected payload sizes and
  keeps browser-side handling trivial; revisitable if profiling shows it
  matters.
- The protocol version lives in the `ready` message rather than in a
  subprotocol negotiation header, so it is observable in logs and replays
  without inspecting the WebSocket handshake.

## Alternatives Considered

### Option A: JSON-RPC 2.0
Well-known, has built-in request/response correlation and error shape. Rejected
because it has no native concept of server-initiated streaming updates (`rx`
would have to be modeled as notifications, losing the symmetry with `ac`), and
its envelope keys (`jsonrpc`, `method`, `params`, `id`) are heavier than
RxDjango's `rx` traffic warrants.

### Option B: Separate message types per kind, no discriminator
E.g. infer kind from which keys are present. Rejected because dispatch then
requires a full parse and a key-presence check, and the protocol becomes
fragile to additive changes — a new optional key on `rx` could be misread as
a different message type.

### Option C: Long, self-descriptive keys (`type`, `field`, `value`, `operation`)
More readable on the wire. Rejected because `rx` messages dominate the byte
budget at runtime; the readability win does not justify the per-message cost,
and tooling can rehydrate short keys for human inspection.

## References

- `0002-core-websocket-protocol.prompt.md`
