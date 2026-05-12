# Counter

A single reactive integer on the channel. Subscribe from React with
`useChannel`, then call `increment` to run the server-side action and
see the value update everywhere it is displayed.

## Backend

```{literalinclude} ../../examples/backend/counter/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/counter/demo.tsx
:language: tsx
```
