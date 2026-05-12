# Memo

Same interaction as Carousel, but fruit and first letter are derived
with `@memo` from `selected`. Useful when you want stable derived
values and explicit dependency tracking on the channel.

## Backend

```{literalinclude} ../../examples/backend/memo/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/memo/MemoPage.tsx
:language: tsx
```
