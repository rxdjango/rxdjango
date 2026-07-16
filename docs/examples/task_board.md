# Task board

Demonstrates the routed (live) tier of the queryset-list architecture
(ADR-0018): `tasks` declares `routing='project_id'` -- a one-word column
sugar that turns the field into a **live** list. A task created under a
watched project, or moved into it, is delivered as it happens: no rebind,
unlike [Static list](static_list)'s unrouted tier, whose one deliverable
limitation is exactly this -- a new row waits for a rebind to appear.
Moving a task to another project delivers the leave signal live too: the
old side of the move disqualifies the row from the connection watching it,
through an ordinary update frame.

```{rxdemo} task_board
```

## Backend

```{literalinclude} ../../examples/backend/task_board/channels.py
:language: python
```

## Models

```{literalinclude} ../../examples/backend/task_board/models.py
:language: python
```

## Serializers

```{literalinclude} ../../examples/backend/task_board/serializers.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/task_board/demo.tsx
:language: tsx
```
