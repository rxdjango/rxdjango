import pytest

from testapp.models import Badge, Company, Employee, Skill, Team


class FakeConsumer:
    def __init__(self):
        self.messages = []

    def enqueue_rx(self, field, value):
        self.messages.append((field, value))


@pytest.fixture
def fake_consumer():
    return FakeConsumer()


@pytest.fixture
def company_tree(db):
    """Deterministic two-level tree covering every relation shape.

    Company #1
      Team #1 'Platform': Alice (skills: Python, TS; badge A-1),
                          Bob   (skills: Python;     badge B-1)
      Team #2 'Design':   Carol (skills: none;       badge C-1)
    Dave (#4) has no team — exercises the nullable forward FK.
    """
    company = Company.objects.create(id=1, name='ACME')
    platform = Team.objects.create(id=1, name='Platform', company=company)
    design = Team.objects.create(id=2, name='Design', company=company)
    alice = Employee.objects.create(id=1, name='Alice', team=platform)
    bob = Employee.objects.create(id=2, name='Bob', team=platform)
    carol = Employee.objects.create(id=3, name='Carol', team=design)
    Employee.objects.create(id=4, name='Dave', team=None)
    python = Skill.objects.create(id=1, name='Python')
    typescript = Skill.objects.create(id=2, name='TypeScript')
    python.employees.set([alice, bob])
    typescript.employees.set([alice])
    Badge.objects.create(id=1, code='A-1', employee=alice)
    Badge.objects.create(id=2, code='B-1', employee=bob)
    Badge.objects.create(id=3, code='C-1', employee=carol)
    return company


@pytest.fixture
def prefetched_company(company_tree):
    """The fully prefetched instance a channel is expected to hand over."""
    return Company.objects.prefetch_related(
        'teams__employees__skills',
        'teams__employees__badge',
    ).get(id=1)
