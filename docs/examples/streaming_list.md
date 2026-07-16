# Streaming list updates

This example shows updates that no client asked for: a background timer
appends one number to `rx[list[int]]` every tick, entirely independent of
any client action. Each tick sends one small update — the message size
never grows with how many items the list already holds.

```{rxdemo} streaming_list
```

## Backend

```{literalinclude} ../../examples/backend/streaming_list/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/streaming_list/demo.tsx
:language: tsx
```
