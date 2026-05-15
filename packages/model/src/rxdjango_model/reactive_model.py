"""The ``ReactiveModel`` base class.

Exposed to application code as ``rxdjango.models.ReactiveModel`` (the
``rxdjango_model`` package installs that import alias — see ``__init__.py``).

A model that inherits ``ReactiveModel`` gains a database-minted, monotonically
increasing ``_v`` version column and broadcasts every committed write to
subscribed clients. Inheritance is the only supported path: a model the
developer does not own cannot be made reactive in place.

See ``docs/adr/0013-reactive-model-base-class.md`` for the rationale, the
concurrency invariants, and why ``QuerySet.update()`` / cascade deletes are out
of scope.
"""
from __future__ import annotations

from functools import partial

from django.db import connections, models, transaction

from .reactive_registry import broadcast_delete, broadcast_instance


class ReactiveModel(models.Model):
    """Abstract base for models whose row changes are pushed to clients.

    Subclasses get a ``_v`` field. It is database-owned and read-only from
    Python: every ``save()`` increments it in a single atomic statement and
    reads the new value back, so the value paired with a broadcast provably
    belongs to that write.
    """

    _v = models.BigIntegerField(default=0, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Persist the row, mint its next ``_v``, and schedule a broadcast.

        The user write and the version bump run inside one ``atomic()`` block,
        so the row lock acquired by the write is held until commit and a
        concurrent writer cannot interleave a version between them. The
        broadcast is deferred to ``on_commit``: in autocommit it fires
        immediately, inside a caller's transaction it fires on that commit.
        """
        with transaction.atomic(using=kwargs.get("using")):
            super().save(*args, **kwargs)
            using = self._state.db
            self._v = self._rx_bump_version(using)
            transaction.on_commit(partial(broadcast_instance, self), using=using)

    def delete(self, *args, **kwargs):
        """Delete the row and schedule a versioned delete event.

        The event is broadcast at ``_v + 1``: nothing can write the row once it
        is gone, so this value is final and always wins over any in-flight
        snapshot of the row a client might still receive.
        """
        using = self._state.db or kwargs.get("using")
        pk = self.pk
        model = type(self)
        version = (self._v or 0) + 1
        result = super().delete(*args, **kwargs)
        if pk is not None:
            transaction.on_commit(
                partial(broadcast_delete, model, pk, version),
                using=using,
            )
        return result

    def _rx_bump_version(self, using: str) -> int:
        """Increment ``_v`` and return the new value in a single statement.

        PostgreSQL and SQLite use ``RETURNING``; MySQL uses
        ``LAST_INSERT_ID(expr)``, which carries the value back on the OK packet
        with no extra roundtrip. The enclosing ``atomic()`` block holds the row
        lock, so the returned value belongs to this write.
        """
        table = self._meta.db_table
        pk_column = self._meta.pk.column
        connection = connections[using]
        with connection.cursor() as cursor:
            if connection.vendor == "mysql":
                cursor.execute(
                    f"UPDATE `{table}` SET `_v` = LAST_INSERT_ID(`_v` + 1) "
                    f"WHERE `{pk_column}` = %s",
                    [self.pk],
                )
                cursor.execute("SELECT LAST_INSERT_ID()")
                return cursor.fetchone()[0]
            cursor.execute(
                f'UPDATE "{table}" SET "_v" = "_v" + 1 '
                f'WHERE "{pk_column}" = %s RETURNING "_v"',
                [self.pk],
            )
            row = cursor.fetchone()
            return row[0] if row else (self._v or 0) + 1
