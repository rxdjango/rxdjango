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
from .routing_registry import (
    broadcast_routed_delete,
    broadcast_routed_write,
    routing_pre_image,
)


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

        For a model with registered routing dimensions (ADR-0018 design D2),
        an update additionally reads a narrow pre-image of the routers' input
        columns *inside this same atomic block* -- before the write, so it
        reflects the row's old value -- gated by ``update_fields`` so a save
        that cannot touch any router's columns skips the read entirely. The
        pre-image is what lets the write path broadcast the leave signal to
        `publish(old)` alongside `publish(new)`.
        """
        with transaction.atomic(using=kwargs.get("using")):
            creating = self._state.adding
            old_pre_image = None
            if not creating and self.pk is not None:
                using_for_read = self._state.db or kwargs.get("using")
                old_pre_image = routing_pre_image(
                    type(self), self.pk, using_for_read, kwargs.get("update_fields"),
                )
            super().save(*args, **kwargs)
            using = self._state.db
            self._v = self._rx_bump_version(using)
            transaction.on_commit(
                partial(_broadcast_saved_row, self, creating, old_pre_image),
                using=using,
            )

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
                partial(_broadcast_deleted_row, self, model, pk, version),
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


def _broadcast_saved_row(instance: 'ReactiveModel', creating: bool, old_pre_image) -> None:
    """`transaction.on_commit` callback for `save()`: the existing
    per-instance broadcast, plus the new dimension-group lifecycle
    broadcast (ADR-0018 design D2) for models with registered routers."""
    broadcast_instance(instance)
    broadcast_routed_write(instance, creating=creating, old_pre_image=old_pre_image)


def _broadcast_deleted_row(instance: 'ReactiveModel', model: type, pk, version: int) -> None:
    """`transaction.on_commit` callback for `delete()`: the existing
    per-instance tombstone, plus the dimension-group tombstone. `instance`
    still carries its pre-delete field values (only its pk attribute was
    cleared by `Model.delete()`), which is exactly what `publish(row)`
    needs."""
    broadcast_delete(model, pk, version)
    broadcast_routed_delete(instance, pk, version)
