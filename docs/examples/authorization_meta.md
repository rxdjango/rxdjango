# Authorization Meta

```{rxdemo} authorization_meta
```

Uses `Meta.action_requires` so every action defaults to requiring
authorization, while `authorize` stays anonymous. Same password flow
as Authorization, but the rule is expressed once on the channel class.

## Backend

```{literalinclude} ../../examples/backend/authorization_meta/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/authorization_meta/demo.tsx
:language: tsx
```
