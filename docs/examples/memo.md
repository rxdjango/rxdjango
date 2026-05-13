# @memo

```{rxdemo} memo
```

This provides the exact same functionality as [rx field](carousel.md) example,
now using `@memo` decorator.

@memo receives a list of `rx` field names that are checked on any update to see
if the value needs to be recalculated.

Inspired by React's useMemo()

## Backend

```{literalinclude} ../../examples/backend/memo/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/memo/demo.tsx
:language: tsx
```
