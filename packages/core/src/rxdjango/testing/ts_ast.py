"""Parse generated TypeScript via the official compiler API.

Shells out to a small Node script that uses the `typescript` package to
walk the AST and emit a JSON description of classes, properties, and
imports. This lets tests assert on structure (class name, heritage,
member type, initializer) without regex matching on source text.
"""
import json
import os
import subprocess
from pathlib import Path

_PARSER_JS = Path(__file__).parent / '_ts_parse.js'


class TSParseError(RuntimeError):
    pass


def _find_node_modules(start: Path) -> Path:
    """Walk up from `start` looking for a node_modules dir containing typescript."""
    for d in [start, *start.parents]:
        candidate = d / 'node_modules' / 'typescript'
        if candidate.is_dir():
            return d / 'node_modules'
    raise TSParseError(
        f'Could not locate node_modules with `typescript` walking up from {start}. '
        'Pass node_modules_dir explicitly to parse_ts_file().'
    )


def parse_ts_file(ts_path, node_modules_dir=None):
    """Parse a .ts file and return a dict: {file, classes, imports, parseErrors}.

    Each class is {name, exported, heritage: [{kind, name}], members: [...]}.
    Property members are {kind: 'property', name, type, initializer, optional, readonly}
    where `type` and `initializer.text` are the verbatim source slices.
    """
    ts_path = str(ts_path)
    if node_modules_dir is None:
        node_modules_dir = _find_node_modules(Path(ts_path).resolve().parent)
    node_modules_dir = str(node_modules_dir)

    env = os.environ.copy()
    existing = env.get('NODE_PATH')
    env['NODE_PATH'] = node_modules_dir + (os.pathsep + existing if existing else '')

    proc = subprocess.run(
        ['node', str(_PARSER_JS), ts_path],
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        raise TSParseError(
            f'node parser failed (exit {proc.returncode}): {proc.stderr.decode()}'
        )
    return json.loads(proc.stdout)


def find_class(parsed, name):
    """Return the class dict named `name` from a parse_ts_file result, or None."""
    for cls in parsed.get('classes', []):
        if cls.get('name') == name:
            return cls
    return None


def find_member(cls, name):
    """Return the member dict named `name` from a class, or None."""
    for m in cls.get('members', []):
        if m.get('name') == name:
            return m
    return None
