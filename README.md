# RxDjango

**Perfectionists with deadlines, end-to-end.**

Django earned its slogan by letting developers express *what* a web app should do and handling the *how*. RxDjango extends that contract across the language boundary — into the SPA frontend, into TypeScript, into real-time — so the same promise holds from the database to the React component.

## Why

Django was built for server-rendered content and DRF extends it for APIs. But the moment a product becomes a single-page app, the developer starts hand-writing the serializer-to-fetcher-to-store-to-component glue. The moment real-time arrives, Django Channels hands over a transport and leaves them alone with consumers, group management, signal wiring, reconnection logic, and message routing — code that has nothing to do with the product.

RxDjango closes that gap. A server-side channel declaration *is* the contract: declare reactive state with the DRF serializers you already write, declare who can write to it, and a typed React SDK is generated from it. Type information and synchronization semantics flow end-to-end. No hand-written consumers, no manual channel groups, no polling, no integration layer to maintain.

## A rebuild

This repository is a ground-up rebuild of RxDjango 0.0.x. The original — [CDIGlobalTrack/rxdjango](https://github.com/CDIGlobalTrack/rxdjango) — has been evolving in production for about five years in a real application and real load. Internals grew complex quickly under the pressure of scale; the semantics came slowly, over years. Those semantics turned out to be the real achievement — and they make most of the original complexity obsolete. This rebuild goes back to front: start from the semantics, then rebuild the internals using pieces of the original where they still fit.

This project was forked from CDIGlobalTrack/rxdjango just for history tracking. The git repository has been built from scratch.

## Layout

```
.
├── packages/
│   ├── python/   # `rxdjango` on PyPI — Django/DRF/Channels backend
│   └── react/    # `@rxdjango/react` on npm — React/TS client
├── examples/     # integration + end-to-end test apps
└── docs/
    └── adr/     # cross-cutting & developer-API decision records
```

Each package and each ADR folder has its own README explaining scope and conventions. The monorepo decision and its trade-offs are captured in [`docs/adr/0001-monorepo-layout.md`](./docs/adr/0001-monorepo-layout.md).
