# Overview

RxDjango exposes Django models and actions as reactive channels. A
client subscribes to a channel, receives a typed initial state, and
then receives diffs as the server-side state changes. Actions are
plain methods on the channel class.

This page will grow into a guided tour. For now, see the
[Quickstart](quickstart.md) for the minimal setup and
[Examples](examples/index.md) for runnable demos.
