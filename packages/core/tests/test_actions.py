"""@action decorator and execute_action dispatch."""
from datetime import datetime

import pytest

from rxdjango import ContextChannel, action, rx
from rxdjango.actions import execute_action, list_actions
from rxdjango.exceptions import ActionNotAsync, ForbiddenError


class Channel(ContextChannel):
    authorized = rx[bool](False)

    @action
    async def echo(self, value: str):
        return value

    @action
    async def schedule(self, when: datetime):
        return when.year

    @action(requires='authorized')
    async def guarded(self):
        return 'secret'

    async def not_an_action(self):
        return 'private'


def test_non_async_action_raises():
    with pytest.raises(ActionNotAsync):
        @action
        def sync_method(self):
            return None


async def test_execute_action_returns_result():
    ch = Channel()
    assert await execute_action(ch, 'echo', ['hi']) == 'hi'


async def test_undecorated_method_is_forbidden():
    ch = Channel()
    with pytest.raises(ForbiddenError):
        await execute_action(ch, 'not_an_action', [])


async def test_missing_method_is_forbidden():
    ch = Channel()
    with pytest.raises(ForbiddenError):
        await execute_action(ch, 'nope', [])


async def test_requires_gates_on_falsy_attribute():
    ch = Channel()
    with pytest.raises(ForbiddenError, match='authorized'):
        await execute_action(ch, 'guarded', [])


async def test_requires_passes_on_truthy_attribute():
    ch = Channel()
    ch.authorized = True
    assert await execute_action(ch, 'guarded', []) == 'secret'


async def test_datetime_param_converted_from_isoformat():
    ch = Channel()
    assert await execute_action(ch, 'schedule', ['2026-07-12T10:00:00']) == 2026


async def test_channel_level_action_requires_applies():
    class Locked(ContextChannel):
        class Meta:
            action_requires = 'ready'

        ready = rx[bool](False)

        @action
        async def act(self):
            return 'done'

        @action(anonymous=True)
        async def open_act(self):
            return 'open'

    ch = Locked()
    with pytest.raises(ForbiddenError):
        await execute_action(ch, 'act', [])
    assert await execute_action(ch, 'open_act', []) == 'open'
    ch.ready = True
    assert await execute_action(ch, 'act', []) == 'done'


def test_list_actions_yields_only_decorated():
    names = {m.__name__ for m in list_actions(Channel)}
    assert names == {'echo', 'schedule', 'guarded'}
