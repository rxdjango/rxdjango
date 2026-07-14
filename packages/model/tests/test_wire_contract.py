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
from asgiref.sync import async_to_sync

from rxdjango_model.fields import _plain
from rxdjango_model.state_model import StateModel

from testapp.serializers import CompanySerializer

WIRE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'contract', 'wire',
)

# transaction=True: serialize_state's layer queries run off the event loop
# via database_sync_to_async, on a thread that can't share a savepoint-based
# django_db transaction with the test's own connection.
pytestmark = pytest.mark.django_db(transaction=True)


def _mark_loaded(data):
    """Recursively inject ``_loaded: True`` the way ``StateBuilder`` does
    client-side (design D5) — every rebuilt instance dict at every nesting
    level, never the server payload itself."""
    if isinstance(data, dict):
        return {**{k: _mark_loaded(v) for k, v in data.items()}, '_loaded': True}
    if isinstance(data, list):
        return [_mark_loaded(item) for item in data]
    return data


def build_contract(state_model, instance):
    async def _collect():
        return [
            entry
            async for _node, layer in state_model.serialize_state(instance)
            for entry in layer
        ]
    payload = async_to_sync(_collect)()
    # What StateBuilder must rebuild is exactly the nested serializer output,
    # plus the client-injected `_loaded: true` on every built instance.
    expected = state_model.nested_serializer.__class__(instance).data
    return {
        'anchor': state_model.instance_type,
        'model': state_model.frontend_model(),
        'payload': _plain(payload),
        'expected': _mark_loaded(_plain(expected)),
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
