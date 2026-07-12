"""@memo reactive property semantics."""
import pytest

from rxdjango import ContextChannel, memo, rx


class Channel(ContextChannel):
    FRUITS = ('apple', 'banana', 'cherry')

    selected = rx[int](0)
    multiplier = rx[int](2)

    @memo('selected')
    def fruit(self):
        return self.FRUITS[self.selected]

    @memo('fruit', 'multiplier')
    def shout(self):
        return f'{self.fruit}!' * self.multiplier


def test_initial_values_computed_at_class_creation():
    ch = Channel()
    assert ch.fruit == 'apple'
    assert ch.shout == 'apple!apple!'


def test_memo_order_respects_dependencies():
    assert Channel._memo_order == ['fruit', 'shout']


def test_dependency_change_recomputes_chain(fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.selected = 2
    assert ch.fruit == 'cherry'
    assert ch.shout == 'cherry!cherry!'
    assert fake_consumer.messages == [
        ('selected', 2),
        ('fruit', 'cherry'),
        ('shout', 'cherry!cherry!'),
    ]


def test_unchanged_value_does_not_recompute_memos(fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.selected = 0
    assert [f for f, _ in fake_consumer.messages] == ['selected']


def test_memo_assignment_raises():
    ch = Channel()
    with pytest.raises(AttributeError, match='read-only'):
        ch.fruit = 'mango'


def test_memo_without_deps_raises():
    with pytest.raises(TypeError, match='at least one dependency'):
        memo()


def test_memo_with_non_string_dep_raises():
    with pytest.raises(TypeError):
        memo(lambda self: None)


def test_unknown_dependency_raises_at_class_creation():
    with pytest.raises(TypeError, match="unknown field 'missing'"):
        class Broken(ContextChannel):
            @memo('missing')
            def value(self):
                return None


def test_circular_dependency_raises_at_class_creation():
    with pytest.raises(TypeError, match='circular'):
        class Circular(ContextChannel):
            @memo('b')
            def a(self):
                return self.b

            @memo('a')
            def b(self):
                return self.a
