"""Marker module for the autodiscovery unit test (ADR-0018 D6, task 1.3).

Nothing in the test suite imports this module directly. Its presence in
`sys.modules` after Django starts up is proof that
`rxdjango.apps.RxDjangoConfig.ready()` autodiscovered and imported it --
exactly the "writer process that never wired up its own import" scenario
the design exists for.
"""

AUTODISCOVERED = True
