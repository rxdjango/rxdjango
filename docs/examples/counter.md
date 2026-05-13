# Basic channel

```{rxdemo} counter
```

This is a simple counter, that demonstrate how state is forwarded to frontend,
and how frontend can interact with backend channel.

The widget at the right (or below depending on your screen) shows the same code
in action.

## Backend

```{literalinclude} ../../examples/backend/counter/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/counter/demo.tsx
:language: tsx
```
