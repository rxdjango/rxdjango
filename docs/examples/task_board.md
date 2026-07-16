# Task board

Adding `routing='project_id'` to a queryset list makes it fully live: a
task created under a watched project, or moved into it, appears the moment
the write commits -- no rebind, unlike
[Static queryset](static_queryset.md), where a new row waits for a rebind.
Moving a task out delivers the removal just as immediately. Routing also
decides what the server sends at all: a connection only receives events
for the projects it watches, so data for other projects never reaches the
client -- while the queryset's other conditions (like this example's
`status='open'`) are applied client-side, on rows already delivered. To
deliberately send a list's events to every connection, declare
`routing=BroadcastRouter()`.

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
