# Queryset Lists (delta)

## MODIFIED Requirements

### Requirement: A list is a queryset assigned to a `many=True` field

The developer surface for a list SHALL be exactly ADR-0019's interface: a
plain Django queryset assigned to a `many=True` `rx.model` field in
`on_connect`. No declaration language, no new verbs. Reassignment
supersedes per `model-state`'s existing semantics. The field's `routing`
declaration (per `list-routing`) selects the tier: without routing the
field is a **static list** (ADR-0018) — snapshot plus updates and deletes
to known rows; rows created after the snapshot do not appear until a
rebind — while with routing the field is **live**: lifecycle events
delivered through the Router's dimension groups enter and leave the list
as they happen.

#### Scenario: Bare queryset binds

- **WHEN** `on_connect` runs `self.tasks = Task.objects.filter(status='open').order_by('-created_at')`
- **THEN** the client receives the field's snapshot and `channel.tasks` derives to the matching rows in descending creation order

#### Scenario: New row does not appear in a static list

- **WHEN** a row matching the queryset's conditions is created after the snapshot and the field declares no routing
- **THEN** the connected client's list is unchanged until the field is rebound

## ADDED Requirements

### Requirement: Routed lists grow membership from qualifying events

For a live (routed) field, the membership basis SHALL grow client-side:
a full-layer anchor row arriving on the field and passing the
descriptor's conditions joins the basis and the derived list, positioned
by the ordering spec. The leave edge needs no new machinery — the
old-side update frame delivered by `publish(old)` fails the conditions
and drops the row through the existing derivation. Static fields keep
cycle 1's never-grow rule. Rebind-authoritative reset and watermark
semantics apply to both tiers unchanged.

#### Scenario: Created row appears live

- **WHEN** a routed list is bound and a row passing its conditions is created
- **THEN** the row's full layer arrives and the derived list gains the row at its ordered position, with no rebind

#### Scenario: Row leaves when routed out

- **WHEN** a member row's update moves it out of the connection's dimension value (e.g. `project_id` 5 → 7) and the queryset filters on that column
- **THEN** the old-side update frame fails the conditions and the row leaves the derived list

#### Scenario: Connections on different dimension values stay isolated

- **WHEN** two connections bind the same routed field with different subscribe values
- **THEN** a creation announces only to the matching connection's list; the other connection receives nothing
