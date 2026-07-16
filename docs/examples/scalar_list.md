# Reactive list of scalars

This example demonstrates `rx[list[str]]`: a reactive list field mutated in
place with ordinary Python list methods. Every `append`, `insert`,
`__setitem__`, `del`, `pop` and reassignment sends a small positional delta
to the client instead of re-sending the whole list, however many items it
holds.

```{rxdemo} scalar_list
```

## Backend

```{literalinclude} ../../examples/backend/scalar_list/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/scalar_list/demo.tsx
:language: tsx
```
