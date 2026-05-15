"""Django ``models`` module for the ``rxdjango_model`` app.

It exists for two reasons:

* Django imports ``<app>.models`` during app population, *after* the app
  registry is ready. ``ReactiveModel`` is a Django model class, so it can only
  be defined at that point — not while ``rxdjango_model/__init__`` is importing.
* ``ReactiveModel`` is meant to be imported from ``rxdjango.models``, alongside
  the rest of the framework surface. ``rxdjango`` core deliberately carries no
  dependency on this package, so rather than a real submodule we alias this
  module into ``sys.modules`` as ``rxdjango.models``. Importing it here — in
  app-population order, with ``rxdjango_model`` ahead of any app that uses
  ``ReactiveModel`` — guarantees the alias is in place before application
  models import it.
"""
import sys

from .reactive_model import ReactiveModel

sys.modules.setdefault('rxdjango.models', sys.modules[__name__])

rxdjango = sys.modules.get('rxdjango')
if rxdjango is not None and not hasattr(rxdjango, 'models'):
    rxdjango.models = sys.modules[__name__]

__all__ = ['ReactiveModel']
