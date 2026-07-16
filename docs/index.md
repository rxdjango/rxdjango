# RxDjango

**Perfectionists with deadlines, end-to-end.**

Django earned its slogan by letting developers express *what* a web app
should do and handling the *how*. RxDjango extends that contract across the
language boundary — into the SPA frontend, into TypeScript, into real-time —
so the same promise holds from the database to the React component.

The moment a product becomes a single-page app, developers start
hand-writing the serializer-to-fetcher-to-store-to-component glue. The
moment real-time arrives, they are handed a transport and left alone with
consumers, channel groups, reconnection logic, and message routing — code
that has nothing to do with the product. RxDjango removes that category of
work: a server-side channel declaration *is* the contract, and a typed
React SDK is generated from it.

A channel declared in Python:

```python
from rxdjango import ContextChannel, rx, action

class CounterChannel(ContextChannel):

    counter = rx[int](0)

    @action
    async def increment(self):
        self.counter += 1
```

becomes a typed React hook, kept in sync over WebSocket:

```tsx
const channel = useChannel(CounterChannel);

<button onClick={channel.increment}>
  {channel.counter}
</button>
```

Start with the [Overview](overview.md), set up with the
[Quickstart](quickstart.md), or see it working in the live
[Examples](examples/index.md).

## Status

RxDjango is a ground-up rebuild of the rxdjango 0.0.x series. Five years of
production use shaped the original's semantics; this rebuild starts from
those semantics with a new architecture and interface, working towards
v0.1. Development happens on
[GitHub](https://github.com/rxdjango/rxdjango) — star the repo to follow
along.

```{toctree}
:maxdepth: 2

overview
quickstart
examples/index
project-status
```
