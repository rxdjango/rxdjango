# AGENTS.md

Guidance for AI assistants working in this repo. For what RxDjango is and why, read `README.md` first.

## How to think about this project

Treat RxDjango as a *semantics project* first and a *plumbing project* second. When evaluating a design choice, weigh it against:

- Does this let the developer express intent more directly, or does it push more mechanics onto them?
- Does this preserve type information across the Python↔TypeScript boundary, or does it leak `any` / dynamic shapes?
- Does this remove a category of boilerplate, or does it just relocate it?

When suggesting features, prefer ones that make the framework's surface smaller and the developer's expression more direct over ones that add knobs. The reactive-models machinery (subscriptions, groups, diffs, caching) is the *means*; the end is a Django+React app where the developer writes serializers, channels, and components, and never writes the glue.

## This is a rebuild

The original (v0.0.x) is the reference for behavior parity — consult it for *what* the framework did, not *how* to structure the new code. It is expected at `./rxdjango-0.0.x/`. If that directory is missing, clone it before reasoning about prior-art behavior:

```bash
git clone https://github.com/CDIGlobalTrack/rxdjango ./rxdjango-0.0.x
```

## Current state

No source code has been written yet. Build, test, and lint commands will be added as the codebase materializes — update this file when they exist.
