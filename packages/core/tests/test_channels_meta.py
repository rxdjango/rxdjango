"""ContextChannelMeta class-creation behavior."""
from rxdjango import ContextChannel, rx
from rxdjango.rx import RxField


def test_rx_fields_collected():
    class Channel(ContextChannel):
        counter = rx[int](0)
        name = rx[str]('x')

    assert set(Channel._rx_fields) == {'counter', 'name'}


def test_non_rx_attributes_ignored():
    class Channel(ContextChannel):
        counter = rx[int](0)
        CONSTANT = 42

        def helper(self):
            return None

    assert set(Channel._rx_fields) == {'counter'}


def test_abstract_channel_is_not_processed():
    class Abstract(ContextChannel):
        class Meta:
            abstract = True

        counter = rx[int](0)

    assert not hasattr(Abstract, '_rx_fields')


def test_meta_action_requires_recorded():
    class Channel(ContextChannel):
        class Meta:
            action_requires = 'authorized'

    assert Channel._action_requires == 'authorized'


def test_no_meta_means_no_action_requires():
    class Channel(ContextChannel):
        counter = rx[int](0)

    assert Channel._action_requires is None


def test_contribute_to_channel_called_at_class_creation():
    calls = []

    class Recording(RxField):
        def contribute_to_channel(self, channel_cls, field_name):
            calls.append((channel_cls, field_name))

    class Channel(ContextChannel):
        tracked = Recording()

    assert calls == [(Channel, 'tracked')]
