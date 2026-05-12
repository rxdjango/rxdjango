# 0004. The `rx[type](default)` reactive field

- **Date:** 2026-05-11
- **Deciders:** Luis Fagundes

## Context

In v0.0.x series, updates were defined by Meta.state and RuntimeState
inner class. That was very nested and non pythonic. For the rebuild, we
start with the latter, runtime reactive variable, to build a solid
primitive syntax. This is the core of RxDjango, and takes the name of "rx",
a reactive field declaration.

The counter and carousel examples show how this new primitive works:

```python
# counter
class CounterChannel(ContextChannel):
    counter = rx[int](0)

    @action
    async def increment(self):
        self.counter += 1
```

```python
# carousel
class CarouselChannel(ContextChannel):
    FRUITS = ['banana', 'apple', 'orange']

    selected = rx[int](0)
    fruit = rx[str](FRUITS[selected])
    first_letter = rx[str](fruit[0])

    @action
    async def rotate(self):
        self.selected = (self.selected + 1) % len(self.FRUITS)
        self.fruit = self.FRUITS[self.selected]
        self.first_letter = self.fruit[0]
```

In the carousel, `FRUITS[selected]` and `fruit[0]` are evaluated at
class-definition time. For those expressions to mean what they read like,
`selected` must behave as an `int` (a valid list index) and `fruit` must
behave as a `str` (subscriptable). The declaration syntax does not get to
be "almost transparent" — it has to be transparent enough that ordinary
Python expressions involving the declared name compose without ceremony.

The codegen story matters in parallel. `makefrontend` needs to read the
declared type and project it to a TypeScript property type, so the type
parameter must be recoverable from the declaration without import-time
annotation parsing.

This ADR pins the declaration. It does not commit to a specific set of
supported value types — that set will grow over time.

## Decision

A reactive field is declared on a `ContextChannel` class body as
`rx[T](default)`:

- `rx[T]` is a type-parameterised factory. `T` is the field's logical
  type — a primitive (`int`, `str`, ...) or, in future, a richer kind to
  be defined by later ADRs.
- `rx[T](default)` produces a descriptor that participates in the
  channel's reactive machinery: reads go through the descriptor, writes
  validate and propagate to the consumer.
- **The object the descriptor exposes for class-body use is itself an
  instance of `T`.** `rx[int](0)` is an `int`; `rx[str]("banana")` is a
  `str`. Class-body expressions like `FRUITS[selected]`, `fruit[0]`,
  `selected + 1` work directly, with no unwrapping, because the operand
  *is* the value.
- The default is positional and (with the exception of None-allowing
  fields, an implementation detail) required. There is no separate
  "annotation form" — `counter: rx[int] = 0` is not part of this
  decision.
- The type parameter is the source of truth for codegen. `makefrontend`
  reads `T` from the descriptor and emits the corresponding TypeScript
  property type on the generated channel class.

The exact set of admissible `T`s and the rules for optional/`None`
handling are deliberately not pinned by this ADR; they are expected to
evolve. What is pinned is the shape `rx[T](default)` and the property
that the resulting object behaves as a `T` in the class body.

## Consequences

### Positive
- Class-body code reads as ordinary Python. `FRUITS[selected]`,
  `fruit[0]`, `selected + 1` need no wrapper-aware idioms; the carousel
  example is legible to a Python developer with no RxDjango knowledge.
- Support for the state is done via special rx fields (to come later),
  so runtime and database states share the same interface style.
- The type parameter is syntactically present and machine-readable at
  class-definition time, so `makefrontend` can derive TypeScript types
  without parsing annotations or running a separate type-checker pass.
- The same surface scales to richer `T`s without changing how a
  declaration is written: a future `rx[list[str]]([])` reads the same as
  `rx[int](0)`.

### Negative / Trade-offs
- Making the descriptor's class-body representative *be* an instance of
  `T` couples the framework to Python's subclassing rules for `T`. Types
  that cannot be subclassed (or that have surprising subclassing
  semantics) are harder to support and may require special-casing.
- `bool` in particular is awkward: instances of an `rx[bool]` subclass
  are not the `True`/`False` singletons, so identity comparisons
  (`flag is True`) silently misbehave. The framework can document this,
  but cannot make it go away. Users who reach for `is` on a reactive
  bool will be wrong, and the wrongness is quiet.
- Operator overloading on the value type leaks through to the
  descriptor. If `T` defines `__getitem__`, then `field[...]` in the
  class body *will* run that operator, which is the desired behaviour
  for the carousel but means the descriptor's surface area is whatever
  `T`'s is — there is no opportunity to add framework methods on the
  descriptor itself without risking collision with `T`'s namespace.

### Neutral
- The set of supported `T`s is intentionally left open. v0.1 starts
  narrow (scalars) and is expected to grow; the surface `rx[T](default)`
  is the same regardless.
- The `rx[T]` syntax mirrors `Generic[T]` / `list[T]` parameterisation
  visually, which sets a reasonable expectation for developers, but the
  framework does not promise full PEP 695 compatibility — `rx` is a
  factory, not a type.


## References

- ADR-0003 — Inherit the ContextChannel surface from rxdjango v0.0.x.
- `examples/backend/counter/channels.py` and
  `examples/backend/carousel/channels.py` — the two reference uses of
  `rx[T](default)`. Counter exercises the read/write path; carousel
  exercises class-body composition that depends on the descriptor's
  representative being an instance of `T`.
- `packages/python/src/rxdjango/rx.py` — current implementation.
