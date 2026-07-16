# Static queryset

Demonstrates the static-queryset-lists tier: `tasks` is a bare Django
queryset assigned once in `on_connect` to a `many=True` `rx.model` field --
no declaration language, no new verbs. Membership is derived entirely on
the client: the snapshot's rows, filtered by the queryset's conditions and
sorted by its ordering, both re-evaluated live as ordinary update frames
arrive. Toggling a task's status flips it out of (or back into) the list;
raising its priority re-sorts it; deleting it removes it. A task created
after the snapshot does not appear until the field is rebound -- the static
tier's one deliberate limitation (no live new-row delivery; that arrives
with the routed tier).

```{rxdemo} static_queryset
```

## Backend

```{literalinclude} ../../examples/backend/static_queryset/channels.py
:language: python
```

## Models

```{literalinclude} ../../examples/backend/static_queryset/models.py
:language: python
```

## Serializers

```{literalinclude} ../../examples/backend/static_queryset/serializers.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/static_queryset/demo.tsx
:language: tsx
```
