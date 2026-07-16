# Static queryset

`tasks` is a bare Django queryset assigned once in `on_connect` to a
`many=True` `rx.model` field -- that one assignment is the whole
declaration. The client keeps the list correct on its own: rows are
filtered by the queryset's conditions and sorted by its ordering,
re-evaluated live as updates arrive. Toggling a task's status flips it out
of (or back into) the list; raising its priority re-sorts it; deleting it
removes it. One deliberate limitation: a task created after the snapshot
appears only when the field is rebound -- for lists where new rows arrive
live, see [Task board](task_board.md).

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
