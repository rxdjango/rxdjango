import asyncio

from rxdjango import ContextChannel, rx, action


class StreamingListChannel(ContextChannel):
    """Background-timer appends to `rx[list[int]]` (ADR-0017): the delta
    story made visible — every tick sends one small insert op, however long
    the list grows, never a full re-send.

    `reactive_model`'s background-work example (`ReactiveModelChannel`) uses
    a real OS `threading.Thread` because its work is a *blocking* Django ORM
    call. This channel's periodic work is a plain `asyncio.sleep` with no
    blocking I/O, so the safe and idiomatic Channels equivalent is an
    `asyncio.Task` cooperating on the consumer's own event loop instead of a
    second OS thread — mutating `self.items` (and flushing the frame it
    enqueues) from a genuinely different thread would race the consumer's
    own coroutine touching the same websocket.
    """

    TICK_SECONDS = 0.3

    items = rx[list[int]]([])
    ticking = rx[bool](True)

    async def on_connect(self):
        self._next_value = 1
        self._task = asyncio.create_task(self._tick_loop())

    async def on_disconnect(self):
        task = getattr(self, '_task', None)
        if task is not None:
            task.cancel()

    async def _tick_loop(self):
        try:
            while True:
                await asyncio.sleep(self.TICK_SECONDS)
                if not self.ticking:
                    continue
                self.items.append(self._next_value)
                self._next_value += 1
                # Nothing calls an action to drive this tick, so nothing
                # would otherwise flush the queued frame (ADR-0017's op
                # rides the same enqueue_rx/_flush_rx path as every other
                # rx update; see consumers.py).
                await self._consumer._flush_rx()
        except asyncio.CancelledError:
            pass

    @action
    async def pause(self):
        self.ticking = False

    @action
    async def resume(self):
        self.ticking = True

    @action
    async def reset(self):
        self.items = []
