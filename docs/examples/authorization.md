# Authorization

```{rxdemo} authorization
```

`increment` is declared with `requires authorized`; `authorize` checks
the password and sets a flag. Until you authorize successfully, the
`increment` action will not run—per-action authorization on the
channel.

## Backend

```{literalinclude} ../../examples/backend/authorization/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/authorization/demo.tsx
:language: tsx
```
