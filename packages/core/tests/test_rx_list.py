"""rx[list[S]] descriptor semantics (ADR-0017).

Declaration-time refusals and accepted shapes, element validation, index
normalization/clamping, per-connection isolation, and wire-shape assertions
via `fake_consumer`. Client-side convergence (a real TS client applying the
emitted ops) is covered by the backend-suite protocol/integration tests.
"""
import pytest

from rxdjango import ContextChannel, rx


class ListChannel(ContextChannel):
    items = rx[list[int]]([1, 2, 3])
    labels = rx[list[str]]([])
    mixed = rx[list[int | str]](['a', 1])
    nullable_items = rx[list[str | None]]([])
    optional_items = rx[list[int] | None]()
    optional_with_default = rx[list[int] | None]([1])


# -- Declaration: refusals -------------------------------------------------


def test_bare_list_refused():
    with pytest.raises(TypeError, match='requires an element type'):
        rx[list]


def test_nested_list_refused():
    with pytest.raises(TypeError, match='must be scalar types'):
        rx[list[list[int]]]


def test_dict_element_refused():
    with pytest.raises(TypeError, match='must be scalar types'):
        rx[list[dict]]


def test_missing_default_raises():
    with pytest.raises(TypeError, match='requires an explicit default'):
        rx[list[int]]()


def test_none_default_on_non_optional_raises():
    with pytest.raises(TypeError, match='default cannot be None'):
        rx[list[int]](None)


def test_bad_default_element_raises():
    with pytest.raises(TypeError):
        rx[list[int]]([1, 'two'])


def test_default_must_be_a_list():
    with pytest.raises(TypeError, match='is not a list'):
        rx[list[int]]('not a list')


def test_list_union_with_non_none_member_refused():
    with pytest.raises(TypeError, match='list field union'):
        rx[list[int] | str]


# -- Declaration: accepted shapes ------------------------------------------


def test_homogeneous_list_default():
    ch = ListChannel()
    assert ch.items == [1, 2, 3]


def test_union_element_list_default():
    ch = ListChannel()
    assert ch.mixed == ['a', 1]


def test_optional_element_list_default():
    ch = ListChannel()
    assert ch.nullable_items == []


def test_optional_field_defaults_to_none():
    ch = ListChannel()
    assert ch.optional_items is None


def test_optional_field_with_default_is_a_list():
    ch = ListChannel()
    assert ch.optional_with_default == [1]


def test_typed_descriptor_is_a_list():
    field = rx[list[int]]([1, 2])
    assert isinstance(field, list)
    assert field == [1, 2]


# -- Per-connection isolation ------------------------------------------


def test_instances_do_not_share_list_state():
    a, b = ListChannel(), ListChannel()
    a.items.append(4)
    assert a.items == [1, 2, 3, 4]
    assert b.items == [1, 2, 3]


def test_mutating_one_instance_does_not_touch_class_default():
    a = ListChannel()
    a.items.append(4)
    b = ListChannel()
    assert b.items == [1, 2, 3]


# -- Element validation ------------------------------------------------


def test_append_wrong_type_raises_and_leaves_list_unchanged():
    ch = ListChannel()
    with pytest.raises(TypeError):
        ch.items.append('x')
    assert ch.items == [1, 2, 3]


def test_insert_wrong_type_raises_and_leaves_list_unchanged():
    ch = ListChannel()
    with pytest.raises(TypeError):
        ch.items.insert(0, 'x')
    assert ch.items == [1, 2, 3]


def test_setitem_wrong_type_raises_and_leaves_list_unchanged():
    ch = ListChannel()
    with pytest.raises(TypeError):
        ch.items[0] = 'x'
    assert ch.items == [1, 2, 3]


def test_extend_validates_every_element_before_mutating():
    ch = ListChannel()
    with pytest.raises(TypeError):
        ch.items.extend([4, 5, 'bad'])
    assert ch.items == [1, 2, 3]


def test_reassignment_validates_elements():
    ch = ListChannel()
    with pytest.raises(TypeError):
        ch.items = [1, 'two']
    assert ch.items == [1, 2, 3]


# -- None-union semantics ------------------------------------------------


def test_mutating_optional_list_holding_none_raises_attribute_error():
    ch = ListChannel()
    with pytest.raises(AttributeError):
        ch.optional_items.append(1)


def test_assigning_list_then_mutating_works():
    ch = ListChannel()
    ch.optional_items = [1, 2]
    ch.optional_items.append(3)
    assert ch.optional_items == [1, 2, 3]


def test_reassigning_to_none_clears_the_list():
    ch = ListChannel()
    ch.optional_items = [1, 2]
    ch.optional_items = None
    assert ch.optional_items is None


def test_non_optional_list_rejects_none_assignment():
    ch = ListChannel()
    with pytest.raises(TypeError):
        ch.items = None


# -- Wire-shape: mutators emit the right op (or replace) ------------------


def test_append_emits_insert_op(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.append(4)
    assert fake_consumer.messages == [('items', [3, 4], 'i')]


def test_insert_clamps_like_python(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.insert(100, 9)  # clamps to len()
    assert ch.items == [1, 2, 3, 9]
    assert fake_consumer.messages == [('items', [3, 9], 'i')]


def test_insert_negative_index_normalizes(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.insert(-1, 9)
    assert ch.items == [1, 2, 9, 3]
    assert fake_consumer.messages == [('items', [2, 9], 'i')]


def test_setitem_emits_set_op(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items[0] = 9
    assert fake_consumer.messages == [('items', [0, 9], 's')]


def test_setitem_negative_index_normalizes(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items[-1] = 9
    assert fake_consumer.messages == [('items', [2, 9], 's')]


def test_delitem_emits_delete_op(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    del ch.items[1]
    assert fake_consumer.messages == [('items', 1, 'd')]


def test_pop_emits_delete_op(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    value = ch.items.pop()
    assert value == 3
    assert fake_consumer.messages == [('items', 2, 'd')]


def test_remove_emits_delete_op(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.remove(2)
    assert fake_consumer.messages == [('items', 1, 'd')]


def test_extend_emits_one_insert_per_element(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.extend([4, 5])
    assert fake_consumer.messages == [
        ('items', [3, 4], 'i'),
        ('items', [4, 5], 'i'),
    ]


def test_iadd_emits_one_insert_per_element(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items += [4, 5]
    assert fake_consumer.messages == [
        ('items', [3, 4], 'i'),
        ('items', [4, 5], 'i'),
    ]


def test_sort_emits_replace(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.sort(reverse=True)
    assert ch.items == [3, 2, 1]
    assert fake_consumer.messages == [('items', [3, 2, 1])]


def test_reverse_emits_replace(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.reverse()
    assert fake_consumer.messages == [('items', [3, 2, 1])]


def test_clear_emits_replace(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.clear()
    assert fake_consumer.messages == [('items', [])]


def test_imul_emits_replace(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items *= 2
    assert ch.items == [1, 2, 3, 1, 2, 3]
    assert fake_consumer.messages == [('items', [1, 2, 3, 1, 2, 3])]


def test_slice_assignment_emits_replace(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items[0:2] = [9, 8, 7]
    assert ch.items == [9, 8, 7, 3]
    assert fake_consumer.messages == [('items', [9, 8, 7, 3])]


def test_slice_deletion_emits_replace(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    del ch.items[0:2]
    assert ch.items == [3]
    assert fake_consumer.messages == [('items', [3])]


def test_reassignment_emits_plain_replace_frame(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items = [9, 8]
    assert fake_consumer.messages == [('items', [9, 8])]


def test_bool_true_is_accepted_as_int_element_parity_with_scalars(fake_consumer):
    # bool is a subclass of int; rx[int] accepts True as a valid int the same
    # way isinstance(True, (int,)) does. list[int] elements share the same
    # isinstance-based validation, so parity holds either way it points.
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.items.append(True)
    assert ch.items[-1] is True
