from django.db import models

from rxdjango.models import ReactiveModel


class VersionedCounter(ReactiveModel):
    """A reactive model exercised by the version-consistency integration test.

    Inheriting ``ReactiveModel`` gives the row a database-minted ``_v`` and a
    broadcast on every committed write — the server half of the consistency
    guarantee the test checks on the client.
    """

    value = models.IntegerField(default=0)
