# Examples

Integration and end-to-end test apps that exercise [`packages/python`](../packages/python) and [`packages/react`](../packages/react) together.

These apps are the reason this project lives in a monorepo: a serializer change, the regenerated TypeScript types, and an integration test against them all land in a single PR and a single CI run.

## Status

Empty. Examples will be added once the rebuild has enough surface to demonstrate.

## Conventions (planned)

Each example is a self-contained Django + React app that:

- Pins a workspace path (or version) of both packages.
- Runs as part of CI on every PR.
- Lives in its own subdirectory with a short README explaining what it demonstrates.
