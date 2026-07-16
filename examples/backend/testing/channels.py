from rxdjango import ContextChannel, rx, action, memo

from static_queryset.models import Task
from static_queryset.serializers import TaskSerializer

from .models import VersionedCounter
from .serializers import VersionedCounterSerializer


class TestingChannel(ContextChannel):

    int_with_default = rx[int](1)
    int_optional = rx[int | None]()

    str_with_default = rx[str]('hello')
    str_optional = rx[str | None]()

    @action
    async def do_action(self, count: int, label: str):
        pass

    async def inert(self):
        pass

    @action
    async def check_optionals_act_as_primitives_when_set(self):
        self.str_optional = 'new string'
        self.int_optional = 3
        self.str_with_default = self.str_optional[
            self.int_with_default:self.int_optional
        ]


class MemoTrackingChannel(ContextChannel):

    field_a = rx[int](0)
    field_b = rx[int](0)

    count_a = rx[int](0)
    count_b = rx[int](0)

    @action
    async def increment_a(self):
        self.field_a = self.field_a + 1

    @action
    async def increment_b(self):
        self.field_b = self.field_b + 1

    @memo('field_a')
    def double_a(self):
        self.count_a = self.count_a + 1
        return self.field_a * 2

    @memo('field_b')
    def double_b(self):
        self.count_b = self.count_b + 1
        return self.field_b * 2


class ListConvergenceChannel(ContextChannel):
    """Exercises the full rx[list[S]] mutator table (ADR-0017 design D2) so
    the backend suite can drive every mutator server-side and assert the
    real TS client's list converges to the server's list.
    """

    items = rx[list[int]]([1, 2, 3])
    optional_items = rx[list[int] | None]()

    @action
    async def do_append(self, value: int):
        self.items.append(value)

    @action
    async def do_insert(self, index: int, value: int):
        self.items.insert(index, value)

    @action
    async def do_setitem(self, index: int, value: int):
        self.items[index] = value

    @action
    async def do_delitem(self, index: int):
        del self.items[index]

    @action
    async def do_remove(self, value: int):
        self.items.remove(value)

    @action
    async def do_pop(self):
        return self.items.pop()

    @action
    async def do_extend(self, values: list[int]):
        self.items.extend(values)

    @action
    async def do_iadd(self, values: list[int]):
        self.items += values

    @action
    async def do_clear(self):
        self.items.clear()

    @action
    async def do_sort(self):
        self.items.sort()

    @action
    async def do_reverse(self):
        self.items.reverse()

    @action
    async def do_imul(self, n: int):
        self.items *= n

    @action
    async def do_slice_assign(self):
        self.items[0:2] = [100, 101, 102]

    @action
    async def do_slice_delete(self):
        del self.items[0:2]

    @action
    async def do_reset(self, values: list[int]):
        self.items = values

    @action
    async def do_burst(self):
        # Interleaved insert/set/delete in one action; frames must arrive in
        # mutation order and the client must converge to the server's list.
        self.items.append(10)
        self.items.insert(0, -1)
        self.items[1] = 999
        del self.items[-1]

    @action
    async def do_append_optional(self, value: int):
        self.optional_items.append(value)

    @action
    async def do_set_optional(self, values: list[int] | None):
        self.optional_items = values

    @action
    async def do_wrong_type_append(self):
        self.items.append('not an int')  # noqa: intentionally invalid


class VersionConsistencyChannel(ContextChannel):
    """Exercises the client-side version watermark (ADR-0014).

    The server subscribes before fetching, so a snapshot can arrive after a
    newer event for the same row. ``on_connect`` reproduces that race
    deterministically: it relays a mock layer carrying a far-newer ``_v``
    *before* fetching the real (older-version) row from the database. A client
    that reconciles by version keeps the mock; one that takes last-write-wins
    by arrival order would be overwritten by the stale snapshot.
    """

    MOCK_VERSION = 1_000_000
    MOCK_VALUE = 999

    counter = rx.model(VersionedCounterSerializer())
    # Set last in on_connect; the client waits on it to know the real
    # (post-mock) snapshot has been delivered and reconciled.
    loaded = rx[bool](False)

    async def on_connect(self):
        # 1. Relay a mock layer with a newer version, ahead of the DB fetch.
        instance_type = type(self)._rx_fields['counter'].state_model.instance_type
        await self._consumer.send_model_layer('counter', {
            '_type': instance_type,
            'id': 1,
            'value': self.MOCK_VALUE,
            '_v': self.MOCK_VERSION,
        })
        # 2. Fetch the real instance (older version) and assign it.
        self.counter = await VersionedCounter.objects.aget(id=1)
        self.loaded = True


class ReconnectChannel(ContextChannel):
    """Exercises the persistent-socket reconnect path (static-queryset-lists
    task 6.3, ADR-0019 D5): `force_disconnect` closes the WebSocket
    server-side, mid-connection, on purpose. The generated client's
    `PersistentSocket` should notice the drop and reconnect with backoff
    entirely on its own; `on_connect` re-runs on the new connection and
    rebinds `tasks` from scratch, so a queued action flushing successfully
    after the drop is proof the client healed and converged.
    """

    tasks = rx.model(TaskSerializer(many=True))

    async def on_connect(self):
        self.tasks = Task.objects.filter(status='open').order_by('id')

    @action
    async def force_disconnect(self):
        # Closes the socket without waiting for this action's own response
        # to be flushed -- the point is an unexpected close from the
        # client's perspective, not a graceful one it requested itself. Any
        # client-visible effect is the WebSocket's `close` event; the code
        # itself (a normal closure) is otherwise irrelevant to the test.
        await self._consumer.close(code=1000)

    @action
    async def ping(self):
        return 'pong'
