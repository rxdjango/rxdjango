# rx fields

```{rxdemo} carousel
```

This example shows how an `rx` field can be used as a bare `str` or `int`.
They are indeed extensions of `int` and `str`.

**NOTE**: `bool` type cannot be extended. `rx[bool]` fields cannot be used with `is` comparison.

## Backend

```{literalinclude} ../../examples/backend/carousel/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/carousel/demo.tsx
:language: tsx
```
