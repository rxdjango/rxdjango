# Docs

Project-wide documentation for RxDjango. Per-package implementation notes live next to each package.

## Contents

- [`adr/`](./adr) — Architecture Decision Records that span more than one package or define the developer-facing API. Implementation-internal ADRs live under each package's own `adr/` folder.

## Planned

- **Wire protocol spec** — the contract between server and client, kept here so any conforming client can be written without reading server code.
- **Guides** — getting started, channel design, authorization, code generation, deployment.

These will land as the rebuild gains surface to document. Until then, the [original 0.0.x docs](https://github.com/CDIGlobalTrack/rxdjango) describe the behavior this project is rebuilding toward.
