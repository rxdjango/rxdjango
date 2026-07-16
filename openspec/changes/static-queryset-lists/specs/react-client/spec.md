# React Client (delta)

## ADDED Requirements

### Requirement: Persistent socket with backoff

The channel's WebSocket SHALL be persistent: on an unexpected close the client reconnects automatically with exponential backoff, resetting the backoff after a successful open. Unmounting (unsubscribing the last subscriber) SHALL stop reconnection. Action requests issued while disconnected are queued and flushed on the next open, per the existing pre-open queue rule.

#### Scenario: Connection heals

- **WHEN** the server drops an open connection while a component stays mounted
- **THEN** the client reconnects with backoff and processes the new ready frame without remounting

#### Scenario: Unmount stops retrying

- **WHEN** the last subscribed component unmounts while the client is between reconnect attempts
- **THEN** no further connection attempts are made

### Requirement: Reconnect is a rebind over a warm index

On reconnect the client SHALL keep its instance index and watermarks and treat the new connection's snapshots as authoritative rebinds (per `queryset-lists`): membership bases reset from the new snapshot anchor frames, re-delivered layers merge idempotently under `_v` watermarks, and scalar fields take the new connection's values.

#### Scenario: Warm reconnect converges

- **WHEN** a client reconnects and the server re-sends a snapshot of rows the client already holds
- **THEN** unchanged rows keep their object references and the derived list equals the server's current queryset result
