# Wire Protocol (delta)

## MODIFIED Requirements

### Requirement: Ready frame opens the conversation

After accepting a connection and running the channel's `on_connect` hook, the server SHALL send `{"t": "ready", "protocol": "<semver>"}` before any other frame. The current protocol version is `0.4.0` (the `q` descriptor's live marker is an additive, minor-version change over `0.3.0`).

#### Scenario: Ready precedes initial state

- **WHEN** a channel assigns reactive state during `on_connect`
- **THEN** the client first receives `{"t": "ready", "protocol": "0.4.0"}`
- **AND** the `rx` frames carrying the assigned state follow the ready frame

### Requirement: Bind descriptor on the `q` slot

The snapshot anchor frame of a `many=True` `rx.model` field SHALL carry the bind descriptor on a `q` key: `{"t": "rx", "f": "<field>", "v": [<anchor layers>], "q": {"w": [[<column>, <lookup>, <value>], ...], "s": ["<column>" | "-<column>", ...]}}` — `w` the conjunction of introspected conditions, `s` the ordering spec with Django's `-` prefix for descending. A routed (live) field's descriptor additionally carries `"l": true`, telling the client the membership basis may grow from qualifying events; static fields omit `l`. `q` marks the frame as an authoritative snapshot: the client resets the field's membership basis to the anchor rows in `v`. `q` SHALL appear only on snapshot anchor frames of `many=True` model fields; subsequent merge frames and all other field kinds never carry it. Frames carrying `q` never carry `o`.

#### Scenario: Snapshot frame carries conditions and ordering

- **WHEN** `on_connect` binds `Task.objects.filter(status='open').order_by('-created_at')`
- **THEN** the field's first frame carries `q` with `w: [["status", "exact", "open"]]` and `s: ["-created_at"]`

#### Scenario: Empty snapshot still carries the descriptor

- **WHEN** the bound queryset matches zero rows
- **THEN** the anchor frame arrives with `v: []` and the `q` descriptor

#### Scenario: Routed field is marked live

- **WHEN** the bound field declares `routing='project_id'`
- **THEN** its snapshot's `q` carries `l: true`
- **AND** a static field's `q` has no `l` key

#### Scenario: Merge frames are plain

- **WHEN** a child layer or a live row update arrives for the same field after the snapshot
- **THEN** the frame carries no `q`
