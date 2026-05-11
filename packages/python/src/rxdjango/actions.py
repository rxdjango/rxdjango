import asyncio
import typing
from datetime import datetime
from .exceptions import ForbiddenError, ActionNotAsync

# A set of references for registered actions, so to protect non-action methods
# from being called by frontend
__actions = set()


_UNSET = object()


def action(method=None, *, requires=_UNSET, anonymous=False):
    """Decorator to expose a ContextChannel method as a frontend-callable RPC action.

    Actions are automatically discovered and exported to the generated TypeScript
    channel class. The method must be async.

    The decorated method's type hints are inspected to auto-convert parameters
    (e.g. ``datetime`` strings are converted to ``datetime`` objects).

    Pass ``requires=<attr>`` to gate the action behind a truthy channel
    attribute. When the attribute is falsy at call time, the action is
    rejected with a 403 response without running the body.

    Example::

        @action
        async def update_status(self, status: str) -> dict:
            self.instance.status = status
            self.instance.save()
            return {"success": True}

        @action(requires='authorized')
        async def increment(self):
            self.counter += 1
    """
    def wrap(method):
        if not asyncio.iscoroutinefunction(method):
            raise ActionNotAsync(f'@action decorator requires "{method.__name__}" to be async')
        wrapped = method
        while getattr(wrapped, '__wrapped__', None):
            wrapped = wrapped.__wrapped__
        __actions.add(wrapped)
        hints = typing.get_type_hints(method)
        hints.pop('return', None)
        hints = list(hints.values())
        method.__datetime_fields = []
        for i in range(len(hints)):
            if hints[i] is datetime:
                method.__datetime_fields.append(i)
        method.__requires = None if requires is _UNSET else requires
        method.__requires_explicit = requires is not _UNSET
        method.__anonymous = anonymous
        return method

    if method is None:
        return wrap
    return wrap(method)


def list_actions(channel):
    """List all decorated methods in this django deployment"""
    for method in channel.__dict__.values():
        try:
            if method in __actions:
                yield method
        except TypeError:
            pass


async def execute_action(channel, method_name, params):
    method = getattr(channel, method_name, None)
    _verify_method(method)
    requires = _resolve_requires(channel, method)
    if requires is not None and not getattr(channel, requires, False):
        raise ForbiddenError(f'Action requires "{requires}"')
    for i in method.__datetime_fields:
        params[i] = datetime.fromisoformat(params[i])
    return await method(*params)


def _verify_method(method):
    """Checks that a method is registered as an action"""
    if not method:
        raise ForbiddenError
    if getattr(method, '__func__', None):
        method = method.__func__
    while getattr(method, '__wrapped__', None):
        method = method.__wrapped__
    if method not in __actions:
        raise ForbiddenError


def _resolve_requires(channel, method):
    func = getattr(method, '__func__', method)
    if getattr(func, '__anonymous', False):
        return None
    if getattr(func, '__requires_explicit', False):
        return getattr(func, '__requires', None)
    return getattr(type(channel), '_action_requires', None)
