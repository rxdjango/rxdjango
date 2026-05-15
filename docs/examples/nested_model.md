# Nested model

Demonstrates a nested serializer: the `User` model has a foreign key to `Company`,
and `UserSerializer` embeds `CompanySerializer`. Both `name` fields stream to the
client through a single `rx.model` declaration.

```{rxdemo} nested_model
```

## Backend

```{literalinclude} ../../examples/backend/nested_model/channels.py
:language: python
```

## Models

```{literalinclude} ../../examples/backend/nested_model/models.py
:language: python
```

## Serializers

```{literalinclude} ../../examples/backend/nested_model/serializers.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/nested_model/demo.tsx
:language: tsx
```
