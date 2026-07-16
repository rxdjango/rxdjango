# Union and optional list elements

This example shows the rest of `rx[list[S]]`'s type surface (ADR-0017):
`list[int | str]` mixes element types in one array, and `list[int] | None`
distinguishes the field being unset (`null`) from being set to an empty list
(`[]`) — two different states at the value tier, not just a naming
convention.

```{rxdemo} list_types
```

## Backend

```{literalinclude} ../../examples/backend/list_types/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/list_types/demo.tsx
:language: tsx
```
