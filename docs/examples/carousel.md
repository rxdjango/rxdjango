# Carousel

Three related reactive fields—selected index, fruit name, and first
letter—updated together when you call `rotate`. Shows how the backend
can keep a small graph of state consistent in one action.

## Backend

```{literalinclude} ../../examples/backend/carousel/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/carousel/demo.tsx
:language: tsx
```
