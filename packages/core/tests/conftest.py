import pytest


class FakeConsumer:
    """Records enqueue_rx calls the way ContextConsumer would receive them."""

    def __init__(self):
        self.messages = []

    def enqueue_rx(self, field, value, op=None):
        if op is None:
            self.messages.append((field, value))
        else:
            self.messages.append((field, value, op))


@pytest.fixture
def fake_consumer():
    return FakeConsumer()
