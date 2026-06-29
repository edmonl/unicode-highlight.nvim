#!/usr/bin/env python3
"""Generate lua/unicode-highlight/data.lua from Unicode source data."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNICODE_SECURITY_VERSION = '16.0.0'
CONFUSABLES_URL = (
    f'https://www.unicode.org/Public/security/{UNICODE_SECURITY_VERSION}/confusables.txt'
)
CONFUSABLES_CACHE = ROOT / 'cache' / f'confusables-{UNICODE_SECURITY_VERSION}.txt'
OVERRIDES_FILE = ROOT / 'data' / 'confusable-overrides.json'
INVISIBLE_FILE = ROOT / 'tools' / 'invisible-character-generator' / 'out' / 'invisible-characters.json'
OUTPUT_FILE = ROOT / 'lua' / 'unicode-highlight' / 'data.lua'

BASIC_ASCII = set(range(0x20, 0x7F))
EXCLUDED_INVISIBLE = {
    0x0009,  # TAB
    0x000A,  # LINE FEED
    0x0020,  # SPACE
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--offline',
        action='store_true',
        help='use the cached confusables.txt and fail if it is missing',
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='download confusables.txt even when the cached copy exists',
    )
    return parser.parse_args()


def read_confusables(offline: bool, refresh: bool) -> str:
    if offline:
        if not CONFUSABLES_CACHE.exists():
            raise FileNotFoundError(
                f'{CONFUSABLES_CACHE} does not exist; run without --offline once first'
            )
        return CONFUSABLES_CACHE.read_text(encoding='utf-8')

    if CONFUSABLES_CACHE.exists() and not refresh:
        return CONFUSABLES_CACHE.read_text(encoding='utf-8')

    with urllib.request.urlopen(CONFUSABLES_URL, timeout=30) as response:
        content = response.read().decode('utf-8')

    CONFUSABLES_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CONFUSABLES_CACHE.write_text(content, encoding='utf-8')
    return content


def first_codepoint(value: str) -> int:
    if not value:
        raise ValueError('expected a non-empty string')
    return ord(value[0])


def parse_confusables(content: str) -> dict[int, int]:
    confusables: dict[int, int] = {}

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        fields = [field.strip() for field in line.split(';')]
        if len(fields) < 2:
            continue

        source = fields[0].split()
        target = fields[1].split()
        if len(source) != 1 or len(target) != 1:
            continue

        confusables[int(source[0], 16)] = int(target[0], 16)

    overrides = json.loads(OVERRIDES_FILE.read_text(encoding='utf-8'))
    for confusable, representant in overrides.items():
        key = first_codepoint(confusable)
        if representant is None:
            confusables.pop(key, None)
        else:
            confusables[key] = first_codepoint(representant)

    return confusables


def confusable_representant(codepoint: int, confusables: dict[int, int]) -> int:
    current = codepoint
    seen = []

    for _ in range(10):
        seen.append(current)
        next_codepoint = confusables.get(current, current)
        if next_codepoint == current:
            return current
        current = next_codepoint

    chain = ' -> '.join(f'U+{codepoint:04X}' for codepoint in seen)
    raise ValueError(f'confusable chain did not converge: {chain}')


def ambiguous_characters(confusables: dict[int, int]) -> dict[int, int]:
    basic_ascii_representants = {
        confusable_representant(codepoint, confusables): codepoint
        for codepoint in BASIC_ASCII
    }

    result: dict[int, int] = {}
    for codepoint in set(confusables.keys()) | set(confusables.values()):
        representant = confusable_representant(codepoint, confusables)
        if representant in basic_ascii_representants and codepoint not in BASIC_ASCII:
            result[codepoint] = basic_ascii_representants[representant]

    return result


def invisible_characters() -> list[int]:
    data = json.loads(INVISIBLE_FILE.read_text(encoding='utf-8'))
    result = set()
    for entry in data:
        codepoint = int(entry['codePoint'])
        if codepoint not in EXCLUDED_INVISIBLE:
            result.add(codepoint)
    return sorted(result)


def utf8_bytes(codepoint: int) -> list[int]:
    return list(chr(codepoint).encode('utf-8'))


def lua_array(values: list[int]) -> str:
    return '{' + ', '.join(str(value) for value in values) + '}'


def ambiguous_lua_table(ambiguous: dict[int, int]) -> str:
    entries = {
        f'    {{ {lua_array(utf8_bytes(codepoint))}, '
        f'{lua_array(utf8_bytes(replacement))}, {codepoint}, {replacement} }}'
        for codepoint, replacement in ambiguous.items()
    }
    return '{\n' + ',\n'.join(sorted(entries)) + '\n}'


def invisible_lua_table(invisible: list[int]) -> str:
    entries = {
        f'{{{lua_array(utf8_bytes(codepoint))}, {codepoint}}}'
        for codepoint in invisible
    }
    return '{ ' + ', '.join(sorted(entries)) + ' }'


def write_lua_data(ambiguous: dict[int, int], invisible: list[int]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        f'''-- This file is auto-generated by scripts/generate_data.py. Do not edit manually!
-- Confusables source: {CONFUSABLES_URL}
-- Invisible source: tools/invisible-character-generator/out/invisible-characters.json

local M = {{}}

M.ambiguous = {ambiguous_lua_table(ambiguous)}

M.invisible = {invisible_lua_table(invisible)}

return M
''',
        encoding='utf-8',
    )


def main() -> int:
    args = parse_args()
    confusables = parse_confusables(read_confusables(args.offline, args.refresh))
    ambiguous = ambiguous_characters(confusables)
    invisible = invisible_characters()
    write_lua_data(ambiguous, invisible)
    print(f'Generated {OUTPUT_FILE.relative_to(ROOT)}')
    print(f'Ambiguous mappings: {len(ambiguous)}')
    print(f'Invisible code points: {len(invisible)}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'error: {exc}', file=sys.stderr)
        raise SystemExit(1)
