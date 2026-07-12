"""rx[T] descriptor semantics."""
import pytest

from rxdjango import ContextChannel, rx


class Channel(ContextChannel):
    counter = rx[int](0)
    name = rx[str]('anonymous')
    ratio = rx[float](1.5)
    selected = rx[bool](True)
    nickname = rx[str | None]()


def test_defaults_returned_before_assignment():
    ch = Channel()
    assert ch.counter == 0
    assert ch.name == 'anonymous'
    assert ch.ratio == 1.5
    assert ch.selected == True  # noqa: E712 — rx[bool] docs mandate equality, not identity
    assert ch.nickname is None


def test_set_and_get_roundtrip():
    ch = Channel()
    ch.counter = 3
    ch.name = 'bob'
    assert ch.counter == 3
    assert ch.name == 'bob'


def test_instances_do_not_share_state():
    a, b = Channel(), Channel()
    a.counter = 7
    assert b.counter == 0


def test_wrong_type_assignment_raises():
    ch = Channel()
    with pytest.raises(TypeError, match="rx field 'counter'"):
        ch.counter = 'seven'


def test_optional_union_accepts_none():
    ch = Channel()
    ch.nickname = 'bo'
    ch.nickname = None
    assert ch.nickname is None


def test_non_optional_rejects_none():
    ch = Channel()
    with pytest.raises(TypeError):
        ch.name = None


def test_required_default_missing_raises():
    with pytest.raises(TypeError, match='requires an explicit default'):
        rx[int]()


def test_none_default_on_non_optional_raises():
    with pytest.raises(TypeError, match='default cannot be None'):
        rx[int](None)


def test_default_type_mismatch_raises():
    with pytest.raises(TypeError):
        rx[int]('zero')


def test_unsupported_type_raises():
    with pytest.raises(TypeError, match='only int, str, float, bool'):
        rx[dict]


def test_typed_descriptor_supports_class_body_expressions():
    # The descriptor instance is a subclass of its base type so class-body
    # expressions like FRUITS[selected] evaluate naturally (ADR-0008).
    field = rx[int](2)
    assert isinstance(field, int)
    assert ('a', 'b', 'c')[field] == 'c'


def test_set_enqueues_rx_message(fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.counter = 5
    assert fake_consumer.messages == [('counter', 5)]


def test_set_without_consumer_is_silent():
    ch = Channel()
    ch.counter = 5  # must not raise
    assert ch.counter == 5
