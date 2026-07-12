"""Wire-contract fixtures shared with the TypeScript suite.

Each JSON file under packages/contract/wire/ pins one protocol exchange:
the flat ``payload`` a channel emits for a known model tree, the ``model``
relation map + ``anchor`` emitted into the generated TS, and the
``expected`` nested object the frontend StateBuilder must rebuild.

This side asserts the Python emitters still produce the fixture; the
vitest suite (packages/react) rebuilds ``payload`` with StateBuilder and
asserts it equals ``expected``. Regenerate with:

    RX_UPDATE_WIRE_FIXTURES=1 uv run pytest packages/model/tests/test_wire_contract.py
"""
import json
import os

import pytest

from rxdjango_model.fields import _plain
from rxdjango_model.state_model import StateModel

from testapp.serializers import CompanySerializer

WIRE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'contract', 'wire',
)

pytestmark = pytest.mark.django_db


def build_contract(state_model, instance):
    payload = [
        entry
        for _node, layer in state_model.serialize_state(instance)
        for entry in layer
    ]
    # What StateBuilder must rebuild is exactly the nested serializer output.
    expected = state_model.nested_serializer.__class__(instance).data
    return {
        'anchor': state_model.instance_type,
        'model': state_model.frontend_model(),
        'payload': _plain(payload),
        'expected': _plain(expected),
    }


def check_fixture(name, contract):
    path = os.path.join(WIRE_DIR, f'{name}.json')
    if os.environ.get('RX_UPDATE_WIRE_FIXTURES'):
        os.makedirs(WIRE_DIR, exist_ok=True)
        with open(path, 'w') as fh:
            json.dump(contract, fh, indent=2, sort_keys=True)
            fh.write('\n')
        return
    with open(path) as fh:
        assert contract == json.load(fh), (
            f'wire contract drifted from {path}; regenerate with '
            'RX_UPDATE_WIRE_FIXTURES=1 if the change is intentional'
        )


def test_company_tree_contract(prefetched_company):
    sm = StateModel(CompanySerializer())
    check_fixture('company_tree', build_contract(sm, prefetched_company))
