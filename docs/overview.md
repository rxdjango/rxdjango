# Overview

In Django, Python code is the source of truth for the database: models
declare the schema, and everything else follows. RxDjango extends that
principle to real-time single-page applications: channels declare the live
state a client sees, and a typed TypeScript SDK follows.

A channel is a Python class — a `ContextChannel` — declared in a
`channels.py` file inside a Django app. It holds the state of one client
connection: plain reactive values, computed fields, or model instances
serialized with the DRF serializers you already write. From these
declarations RxDjango generates a matching TypeScript class for the
frontend.

At runtime, each connected client gets a live instance of the channel.
Assigning to a field on the server pushes the new value to the frontend
automatically, and the frontend calls the channel's actions like ordinary
async methods — no hand-written consumers, no channel groups, no message
routing on either side.

See the [Quickstart](quickstart.md) for setup, and try the
[Examples](examples/index.md) to interact with each feature live.
