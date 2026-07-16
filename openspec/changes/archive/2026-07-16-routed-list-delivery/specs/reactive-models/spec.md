# Reactive Models (delta)

## MODIFIED Requirements

### Requirement: Broadcasts reach exactly the clients holding the row

A broadcast group SHALL exist per (serializer type, row id); a connection joins the group of every reactive instance it relays and leaves it when the row is deleted or the connection closes. A row change is delivered once per serializer shape registered for the model, only to subscribed connections, and is routed on arrival to the `rx.model` field that holds the row. In addition, a model with registered routing dimensions (per `list-routing`) SHALL broadcast committed writes to the dimension groups of `publish(row)` — `publish(old) ∪ publish(new)` for updates, using the gated pre-image read — so connections with no prior relationship to the row receive its lifecycle events; duplicate delivery of one write through a per-instance group and a dimension group is harmless by `_v` reconciliation.

#### Scenario: Only holders are notified

- **WHEN** two clients are connected and only one has relayed project 1
- **THEN** saving project 1 pushes a frame to that client alone

#### Scenario: Creation reaches a dimension subscriber

- **WHEN** a connection is subscribed to a routing dimension value and a new row announcing to that value is created
- **THEN** the connection receives the row's layer although it never relayed the row

#### Scenario: Duplicate delivery converges

- **WHEN** a connection holds a row through its per-instance group and is also subscribed to the row's dimension group
- **THEN** an update may arrive twice with the same `_v` and the client applies it once
