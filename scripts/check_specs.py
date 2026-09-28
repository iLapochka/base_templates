"""Validate the specs tree so `specs/INDEX.md` stays a usable lookup mechanism."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SPECS_DIR = Path('specs')
INDEX = SPECS_DIR / 'INDEX.md'
TYPES = ('unit', 'integration', 'contract', 'flow')
REQUIRED_KEYS = ('type', 'name', 'created')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def split_frontmatter(text: str) -> str | None:
    """Return the YAML frontmatter block, or None when the file has none."""
    if not text.startswith('---\n'):
        return None
    end = text.find('\n---', 4)
    return None if end == -1 else text[4:end]


def parse_frontmatter(block: str) -> tuple[dict[str, str], list[str]]:
    """Parse the flat subset of YAML the spec format uses: scalars and one list."""
    scalars: dict[str, str] = {}
    context: list[str] = []
    current_key: str | None = None

    for raw_line in block.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue
        if raw_line.startswith((' ', '\t')):
            item = raw_line.strip()
            if item.startswith('- ') and current_key == 'context':
                context.append(item[2:].strip().strip('"\''))
            continue
        key, _, value = raw_line.partition(':')
        current_key = key.strip()
        cleaned = value.strip().strip('"\'')
        if cleaned:
            scalars[current_key] = cleaned

    return scalars, context


def check_spec(path: Path, index_text: str) -> list[str]:
    """Return the problems found in a single spec file."""
    problems: list[str] = []
    relative = path.as_posix()

    parts = path.parts
    spec_type = parts[1] if len(parts) > 2 else None
    if spec_type not in TYPES:
        expected = '|'.join(TYPES)
        problems.append(f'{relative}: must live under specs/<{expected}>/<context>/<name>.md')

    block = split_frontmatter(path.read_text(encoding='utf-8'))
    if block is None:
        problems.append(f'{relative}: missing YAML frontmatter')
        return problems

    scalars, context = parse_frontmatter(block)

    problems.extend(
        f'{relative}: frontmatter is missing `{key}`'
        for key in REQUIRED_KEYS
        if key not in scalars
    )

    declared = scalars.get('type')
    if declared and declared not in TYPES:
        expected = ', '.join(TYPES)
        problems.append(f'{relative}: unknown type `{declared}` (expected one of {expected})')
    elif declared and spec_type in TYPES and declared != spec_type:
        problems.append(
            f'{relative}: frontmatter type `{declared}` does not match directory `{spec_type}`',
        )

    created = scalars.get('created')
    if created and not DATE_RE.match(created):
        problems.append(f'{relative}: `created: {created}` must be YYYY-MM-DD')

    problems.extend(
        f'{relative}: context file does not exist: {target}'
        for target in context
        if not Path(target).exists()
    )

    # The index lists specs by their kebab-case stem, not by full path.
    if path.stem not in index_text:
        problems.append(
            f'{relative}: not listed in {INDEX.as_posix()} — add it (see Step 5 of the skill)',
        )

    return problems


def main(argv: list[str]) -> int:
    """Check the specs given on the command line, or the whole `specs/` tree."""
    if not SPECS_DIR.is_dir():
        return 0
    if not INDEX.is_file():
        sys.stderr.write(f'{INDEX.as_posix()} is missing — it is the spec lookup mechanism.\n')
        return 1

    index_text = INDEX.read_text(encoding='utf-8')
    candidates = [Path(arg) for arg in argv] if argv else sorted(SPECS_DIR.rglob('*.md'))

    problems: list[str] = []
    for path in candidates:
        if path.suffix != '.md' or not path.is_file() or path.name == 'INDEX.md':
            continue
        if SPECS_DIR not in path.parents:
            continue
        problems.extend(check_spec(path, index_text))

    if not problems:
        return 0

    sys.stderr.write('Spec problems:\n')
    for problem in problems:
        sys.stderr.write(f'  {problem}\n')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
