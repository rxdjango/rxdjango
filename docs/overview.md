# Overview

In Django, Python code is the source of truth for databases.
RxDjango extends this principle to generate SDKs for real-time
single page applications (SPAs).

Developer declares `ContextChannel` classes in `channels.py` file
inside each app. For each context channel, a matching Typescript
class is created. The Python instance of the channel holds the
context in memory, and updates are automatically forward to the
frontend's state. Frontend can call methods directly using RPC,
with a matching interface for the backend class.

See the [Quickstart](quickstart.md) for setup and check the
[Examples](examples/index.md) on how it works.
