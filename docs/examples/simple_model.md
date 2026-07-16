# Simple model

This example introduces `rx.model`: a channel field holding a Django model
instance, serialized with a DRF serializer you already write. Assigning an
instance to the field delivers its serialized data to the frontend, typed
to match the serializer.

```{rxdemo} simple_model
```

## Backend

```{literalinclude} ../../examples/backend/simple_model/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/simple_model/demo.tsx
:language: tsx
```
