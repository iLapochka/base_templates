"""Enforce the dependency rule from CLAUDE.md: imports may only point inward."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Frameworks, drivers and clients that must never reach the hexagon.
OUTSIDE_PACKAGES = frozenset(
    {
        'aiosqlite',
        'alembic',
        'asyncpg',
        'cv2',
        'fastapi',
        'ffmpeg',
        'httpx',
        'os',
        'PIL',
        'sqladmin',
        'sqlalchemy',
        'starlette',
        'subprocess',
        'uvicorn',
        'yt_dlp',
    },
)

# Stdlib the hexagon needs (`asyncio` for timeouts), minus the parts that start a process.
OUTSIDE_SUBMODULES = ('asyncio.subprocess',)
PROCESS_CALLS = frozenset({'create_subprocess_exec', 'create_subprocess_shell'})

# Entities are plain dataclasses, not pydantic models — see CLAUDE.md, Architecture.
DOMAIN_EXTRA_FORBIDDEN = frozenset({'pydantic', 'pydantic_settings'})

# Within `src`, a layer is a path segment rather than the root package: every
# internal import reads as root `src`, so `from src.accounts.presentation...`
# looks harmless until the segments are examined. These are the segments each
# inner layer must never reach for.
FORBIDDEN_SRC_LAYERS: dict[str, frozenset[str]] = {
    'domain': frozenset({'application', 'infrastructure', 'presentation'}),
    'application': frozenset({'infrastructure', 'presentation'}),
}

# The same rule at the root-package level: the outer layers, plus `core` and the
# libraries that live there.
RULES: dict[str, frozenset[str]] = {
    layer: OUTSIDE_PACKAGES | forbidden_layers | {'core'}
    for layer, forbidden_layers in FORBIDDEN_SRC_LAYERS.items()
}
RULES['domain'] |= DOMAIN_EXTRA_FORBIDDEN

# Layers that sit outside the hexagon: present in the tree, never checked.
OUTER_LAYERS = frozenset({'presentation', 'infrastructure'})


def layer_of(path: Path) -> str | None:
    """Return the DDD layer a file belongs to, or None when it is not layered code."""
    parts = path.parts
    if 'src' not in parts:
        return None
    for part in parts[parts.index('src') + 1 :]:
        if part in RULES or part in OUTER_LAYERS:
            return part
    return None


def package_of(path: Path) -> list[str]:
    """The dotted package a file lives in, from `src` down, as a relative import resolves it."""
    parts = list(path.with_suffix('').parts)
    parts = parts[parts.index('src') :] if 'src' in parts else parts
    return parts if path.name == '__init__.py' else parts[:-1]


def imported_modules(tree: ast.AST, path: Path) -> list[tuple[str, int]]:
    """Collect (dotted module name, line number) for every import, relative ones resolved."""
    found: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            # `from ..infrastructure import x` climbs level-1 packages above this file's own.
            package = package_of(path)
            base = package[: len(package) - node.level + 1] if node.level else []
            module = '.'.join([*base, *([node.module] if node.module else [])])
            found.add((module, node.lineno))
            # `from src.jobs import infrastructure` names the layer as an imported name.
            for alias in node.names:
                found.add((f'{module}.{alias.name}', node.lineno))
    return sorted(found, key=lambda item: item[1])


def outer_layer_in(module: str, forbidden_layers: frozenset[str]) -> str | None:
    """Return the outer layer an internal import reaches into, if it does."""
    segments = module.split('.')
    if segments[0] != 'src':
        return None
    return next((segment for segment in segments[1:] if segment in forbidden_layers), None)


def check(path: Path) -> list[str]:
    """Return the layering violations in a single file."""
    layer = layer_of(path)
    if layer not in RULES:
        return []

    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError as exc:  # ruff reports the syntax error itself
        return [f'{path}: cannot parse ({exc.msg})']

    violations: list[str] = []
    for module, lineno in imported_modules(tree, path):
        root = module.split('.')[0]
        if root in RULES[layer]:
            violations.append(f'{path}:{lineno}: `{layer}` must not import `{root}`')
            continue
        if module.startswith(OUTSIDE_SUBMODULES):
            violations.append(f'{path}:{lineno}: `{layer}` must not import `{module}`')
            continue
        outer = outer_layer_in(module, FORBIDDEN_SRC_LAYERS[layer])
        if outer:
            violations.append(
                f'{path}:{lineno}: `{layer}` must not import `{module}` '
                f'— `{outer}` is an outer layer',
            )
    # `asyncio.create_subprocess_exec(...)` starts ffmpeg without importing anything forbidden.
    violations.extend(
        f'{path}:{node.lineno}: `{layer}` must not start a process — go through a port'
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr in PROCESS_CALLS)
        or (isinstance(node, ast.Name) and node.id in PROCESS_CALLS)
        or (isinstance(node, ast.ImportFrom) and any(a.name in PROCESS_CALLS for a in node.names))
    )
    return violations


def main(argv: list[str]) -> int:
    """Check the files given on the command line, or the whole `src/` tree."""
    if argv:
        files = [Path(arg) for arg in argv]
    elif Path('src').is_dir():
        files = sorted(Path('src').rglob('*.py'))
    else:
        files = []

    violations: list[str] = []
    for path in files:
        if path.suffix == '.py' and path.is_file():
            violations.extend(check(path))

    if not violations:
        return 0

    sys.stderr.write('DDD layering violations (imports must point inward only):\n')
    for violation in violations:
        sys.stderr.write(f'  {violation}\n')
    sys.stderr.write(
        '\nDeclare the dependency as an abstract repository in '
        '`src/<domain>/domain/repositories/` and implement it in '
        '`src/<domain>/infrastructure/repositories/`. See CLAUDE.md, Rules.\n',
    )
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
