# Reactive model

Demonstrates that model changes made outside the channel context — such as in a
background thread or a separate process — are pushed reactively to connected
clients. A `modify_project` action spawns a thread that sleeps for a configurable
delay, then fetches the `Project` from the database and saves a new name. The
frontend receives the updated `Task` (with its nested `Project`) automatically,
without any manual refresh.

```{rxdemo} reactive_model
```

## Backend

```{literalinclude} ../../examples/backend/reactive_model/channels.py
:language: python
```

## Models

```{literalinclude} ../../examples/backend/reactive_model/models.py
:language: python
```

## Serializers

```{literalinclude} ../../examples/backend/reactive_model/serializers.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/reactive_model/demo.tsx
:language: tsx
```
