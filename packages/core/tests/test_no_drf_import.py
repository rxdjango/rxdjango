"""The core package must be importable without ever pulling in DRF.

The dependency split (rxdjango = Django + channels only; rxdjango_model owns
the DRF integration) is a package-structure promise; this guards it at the
import level, which is stronger than what the venv contains.
"""
import subprocess
import sys

CODE = '\n'.join([
    'import sys',
    'import rxdjango',
    'import rxdjango.actions',
    'import rxdjango.channels',
    'import rxdjango.consumers',
    'import rxdjango.exceptions',
    'import rxdjango.memo',
    'import rxdjango.rx',
    'import rxdjango.sdk',
    'import rxdjango.ts.channels',
    "assert 'rest_framework' not in sys.modules, 'rxdjango core imported DRF'",
])


def test_core_never_imports_drf():
    result = subprocess.run(
        [sys.executable, '-c', CODE],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
