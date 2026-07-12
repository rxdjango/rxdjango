import pytest


class FakeConsumer:
    """Records enqueue_rx calls the way ContextConsumer would receive them."""

    def __init__(self):
        self.messages = []

    def enqueue_rx(self, field, value):
        self.messages.append((field, value))


@pytest.fixture
def fake_consumer():
    return FakeConsumer()
