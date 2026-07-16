# Quickstart

This walkthrough sets up a minimal RxDjango app: a Django channel holding
one reactive value, and a React component bound to it. RxDjango is working
towards v0.1 and is not yet published on PyPI or npm — both packages
install from the git repository for now.

## Prerequisites

- A Django project served over ASGI with
  [Channels](https://channels.readthedocs.io/) installed.
- A running Redis. RxDjango broadcasts updates through the Channels
  channel layer, and the in-memory layer does not work across processes —
  use `channels_redis`.
- A React app for the frontend.

## Install

The backend package lives in the monorepo under `packages/core`:

```bash
pip install "rxdjango @ git+https://github.com/rxdjango/rxdjango#subdirectory=packages/core"
```

Model-backed state (`rx.model`, DRF serializers, reactive Django models)
comes from a second package:

```bash
pip install "rxdjango-model @ git+https://github.com/rxdjango/rxdjango#subdirectory=packages/model"
```

The React client is built from the repo and installed from its local path:

```bash
git clone https://github.com/rxdjango/rxdjango
cd rxdjango/packages/react
npm install && npm run build
cd /path/to/your-app
npm install /path/to/rxdjango/packages/react
```

## Configure Django

In `settings.py`, add the apps and point RxDjango at your frontend:

```python
INSTALLED_APPS = [
    # ...
    'rxdjango',
    'channels',
    # your apps
]

ASGI_APPLICATION = 'backend.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': ['redis://127.0.0.1:6379/0']},
    },
}

# Where generated TypeScript files are written, inside your React app.
RX_FRONTEND_DIR = BASE_DIR / '../frontend/src/app/rx'

# A JavaScript expression for the WebSocket URL, embedded in the
# generated client.
RX_WEBSOCKET_URL = "'ws://localhost:8000'"
```

## Declare a channel

In an app's `channels.py`:

```python
from rxdjango import ContextChannel, rx, action

class CounterChannel(ContextChannel):

    counter = rx[int](0)

    @action
    async def increment(self):
        self.counter += 1
```

Route it in the app's `urls.py` and include it in your ASGI websocket
router:

```python
from django.urls import path
from .channels import CounterChannel

websocket_urls = [
    path('ws/counter/', CounterChannel.as_asgi()),
]
```

```python
# asgi.py
from channels.routing import ProtocolTypeRouter, URLRouter
from counter.urls import websocket_urls

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(websocket_urls),
})
```

## Generate the TypeScript client

```bash
./manage.py makefrontend
```

This writes one module per app under `RX_FRONTEND_DIR` — for the channel
above, `rx/counter/counter.channels.ts`, exporting a typed
`CounterChannel`. Re-run it whenever a channel changes; it only rewrites
files whose declarations changed.

## Use it from React

```tsx
import { useChannel } from '@rxdjango/react';
import { CounterChannel } from './rx/counter/counter.channels';

export function Counter() {
  const channel = useChannel(CounterChannel);

  return (
    <button onClick={channel.increment}>
      {channel.counter}
    </button>
  );
}
```

`useChannel` opens the WebSocket, keeps `channel.counter` in sync with the
server, re-renders on every update, and exposes `increment` as a typed
async method. That is the whole integration — there is no consumer,
fetcher, or store to write.

From here, the [Examples](examples/index.md) walk through the rest of the
surface: computed fields, authorization, model-backed state, reactive
lists, and live querysets.
