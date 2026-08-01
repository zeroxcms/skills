#!/usr/bin/env python3
"""Inspect a compiled Tailwind stylesheet (the host CMS's admin.css) and report
which utility classes it actually emits.

Why this exists: a Workers CMS plugin borrows the host's *purged* compiled CSS,
so any class the host doesn't use is silently absent. Before using a class in a
plugin view, confirm it's present here.

Usage:
    # Dump the available class set, grouped by prefix:
    python check_classes.py path/to/admin.css

    # Check specific candidate classes (PRESENT / MISSING):
    python check_classes.py path/to/admin.css --check "grid-cols-3 w-1/3 max-w-[9rem]"

    # Check a newline/space/comma list from a file (e.g. classes you used):
    python check_classes.py path/to/admin.css --file used-classes.txt

Exit code is non-zero if any checked class is MISSING, so it's CI-friendly.
"""
import argparse
import re
import sys
from collections import defaultdict


def extract_classes(css: str) -> set[str]:
    """Return the set of class names defined as selectors in the CSS.

    Tailwind escapes special chars in selectors (e.g. `.sm\\:grid-cols-2`,
    `.min-w-\\[9rem\\]`, `.w-1\\/3`). We capture the escaped selector token and
    unescape it back to the authoring form the user writes in markup.
    """
    names: set[str] = set()
    # A class selector: a dot followed by escaped-or-plain selector chars,
    # optionally with escaped pseudo segments (\:hover etc.) — but we want the
    # full authoring name including variants like `sm:` and `hover:`.
    for m in re.finditer(r'\.((?:\\.|[A-Za-z0-9_-])+(?:\\:[A-Za-z0-9_-]+)*)', css):
        name = re.sub(r'\\(.)', r'\1', m.group(1))
        # Drop false positives from CSS value tokens (e.g. `.025em`, `.5`): real
        # Tailwind class names start with a letter or `-` and contain a letter.
        if not re.match(r'^[A-Za-z-]', name) or not re.search(r'[A-Za-z]', name):
            continue
        names.add(name)
    return names


def parse_candidates(raw: str) -> list[str]:
    return [c for c in re.split(r'[\s,]+', raw.strip()) if c]


def group_key(name: str) -> str:
    # Group by the leading utility family for readable output.
    base = name.split(':')[-1]  # drop variant prefix for grouping
    m = re.match(r'([a-z]+(?:-[a-z]+)?)', base)
    return m.group(1) if m else base


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('css', help='Path to the compiled admin.css')
    ap.add_argument('--check', help='Space/comma separated class names to verify')
    ap.add_argument('--file', help='File of class names (space/newline/comma separated)')
    args = ap.parse_args()

    try:
        css = open(args.css, encoding='utf-8').read()
    except OSError as e:
        print(f'error: cannot read {args.css}: {e}', file=sys.stderr)
        return 2

    available = extract_classes(css)

    candidates: list[str] = []
    if args.check:
        candidates += parse_candidates(args.check)
    if args.file:
        candidates += parse_candidates(open(args.file, encoding='utf-8').read())

    if candidates:
        missing = []
        width = max(len(c) for c in candidates)
        for c in candidates:
            ok = c in available
            print(f'{c:<{width}}  {"PRESENT" if ok else "MISSING"}')
            if not ok:
                missing.append(c)
        if missing:
            print(f'\n{len(missing)} MISSING: ' + ' '.join(missing), file=sys.stderr)
            return 1
        print(f'\nAll {len(candidates)} present.')
        return 0

    # No candidates: dump the available set grouped by family.
    groups: dict[str, list[str]] = defaultdict(list)
    for n in available:
        groups[group_key(n)].append(n)
    print(f'{len(available)} utility classes available in {args.css}\n')
    for key in sorted(groups):
        vals = sorted(groups[key])
        print(f'{key} ({len(vals)}): ' + ' '.join(vals))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
