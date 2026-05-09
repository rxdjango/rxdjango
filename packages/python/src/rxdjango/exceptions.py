"""RxDjango exception classes.

Custom exceptions used throughout the RxDjango framework
"""


class ForbiddenError(Exception):
    """Raised when an authenticated user lacks permission to access a channel.

    Occurs when ``has_permission()`` on the ContextChannel returns ``False``
    for the authenticated user, resulting in a 403-equivalent rejection.
    """
    pass


class ActionNotAsync(Exception):
    """Raised when an ``@action``-decorated method is not an async function.

    All action methods on ContextChannel subclasses must be defined with
    ``async def``. This exception is raised during channel metaclass
    initialization if a synchronous method is decorated with ``@action``.
    """
    pass


class InvalidMessageReceived(Exception):
    pass
