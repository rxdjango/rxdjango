from rxdjango import ContextChannel, rx, action, memo

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
