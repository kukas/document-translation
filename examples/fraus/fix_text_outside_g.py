#!/usr/bin/env python3
"""
fix_text_outside_g.py

Reads a file where each line contains inline XML-like markup (<g>, <x> tags).
Ensures that no non-whitespace text appears outside <g> elements.
Any such text is merged into the immediately preceding <g> closing tag
(preferred) or, if none exists before it, into the immediately following
<g> opening tag.  A warning is printed for every fix applied.

Usage:
    python fix_text_outside_g.py input.txt output.txt
    python fix_text_outside_g.py input.txt output.txt --strict   # exit 1 if any fix was needed
"""

import re
import sys
import argparse
import logging

# Tokeniser: splits a line into a sequence of (kind, value) pairs where kind is
#   'open_g'   – <g ...>
#   'close_g'  – </g>
#   'self'     – self-closing tag or <x .../> style tag
#   'text'     – anything else (plain text, possibly containing spaces)
TOKEN_RE = re.compile(
    r'(<g(?:\s[^>]*)?>)'     # group 1 – opening <g>
    r'|(</g>)'                # group 2 – closing </g>
    r'|(</?[a-zA-Z][^>]*/?>)' # group 3 – other tags (self-closing or unknown)
    r'|([^<]+)'               # group 4 – text node
    r'|(<[^>]*>)',            # group 5 – any remaining tag
    re.DOTALL
)


def tokenise(line: str):
    """Return list of (kind, value) tokens for one line."""
    tokens = []
    for m in TOKEN_RE.finditer(line):
        if m.group(1):
            tokens.append(('open_g', m.group(1)))
        elif m.group(2):
            tokens.append(('close_g', m.group(2)))
        elif m.group(3):
            tokens.append(('other_tag', m.group(3)))
        elif m.group(4):
            tokens.append(('text', m.group(4)))
        elif m.group(5):
            tokens.append(('other_tag', m.group(5)))
    return tokens


def g_depth(tokens, idx):
    """Return the nesting depth of <g> tags at position idx (before token idx)."""
    depth = 0
    for i in range(idx):
        if tokens[i][0] == 'open_g':
            depth += 1
        elif tokens[i][0] == 'close_g':
            depth -= 1
    return depth


def fix_line(line: str, lineno: int, logger: logging.Logger) -> str:
    """
    Fix a single line so that no non-whitespace text appears outside <g> tags.
    Returns the (possibly modified) line.
    """
    tokens = tokenise(line)
    changed = True
    passes = 0
    while changed:
        changed = False
        passes += 1
        if passes > len(tokens) + 1:
            # safety guard against infinite loops
            break
        for idx, (kind, value) in enumerate(tokens):
            if kind != 'text':
                continue
            if not value.strip():
                # pure whitespace outside <g> is acceptable
                continue
            depth = g_depth(tokens, idx)
            if depth > 0:
                # text is already inside a <g>, fine
                continue

            # --- text is outside <g> ---
            # Try to find the nearest preceding close_g
            prev_close = None
            for j in range(idx - 1, -1, -1):
                if tokens[j][0] == 'close_g':
                    prev_close = j
                    break
                if tokens[j][0] in ('open_g', 'other_tag'):
                    break

            # Try to find the nearest following open_g
            next_open = None
            for j in range(idx + 1, len(tokens)):
                if tokens[j][0] == 'open_g':
                    next_open = j
                    break
                if tokens[j][0] in ('close_g', 'other_tag'):
                    break

            if prev_close is not None:
                # insert text before the closing </g>
                logger.warning(
                    "Line %d: non-<g> text %r moved into preceding <g> element.",
                    lineno, value
                )
                tokens[prev_close] = ('close_g', value + tokens[prev_close][1])
                tokens.pop(idx)
            elif next_open is not None:
                # insert text after the opening <g>
                logger.warning(
                    "Line %d: non-<g> text %r moved into following <g> element.",
                    lineno, value
                )
                tokens[next_open] = ('open_g', tokens[next_open][1] + value)
                tokens.pop(idx)
            else:
                logger.error(
                    "Line %d: non-<g> text %r found but no adjacent <g> element "
                    "to attach it to – left unchanged.",
                    lineno, value
                )
                continue

            changed = True
            break  # restart scan after modification

    return ''.join(v for _, v in tokens)


def process(input_path: str, output_path: str, strict: bool, logger: logging.Logger) -> int:
    """Process input file and write fixed output.  Returns number of warnings."""
    warning_count = 0

    class CountingHandler(logging.Handler):
        def emit(self, record):
            nonlocal warning_count
            if record.levelno >= logging.WARNING:
                warning_count += 1

    logger.addHandler(CountingHandler())

    with open(input_path, 'r', encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8') as fout:
        for lineno, line in enumerate(fin, start=1):
            fixed = fix_line(line.rstrip('\n'), lineno, logger)
            fout.write(fixed + '\n')

    return warning_count


def main():
    parser = argparse.ArgumentParser(
        description='Ensure all non-whitespace text is inside <g> elements.'
    )
    parser.add_argument('input_file', help='Input file path')
    parser.add_argument('output_file', help='Output file path')
    parser.add_argument(
        '--strict', action='store_true',
        help='Exit with code 1 if any text was moved (i.e. fixes were applied)'
    )
    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=logging.DEBUG,
        stream=sys.stderr
    )
    logger = logging.getLogger('fix_text_outside_g')

    warnings = process(args.input_file, args.output_file, args.strict, logger)

    if warnings:
        logger.info('%d fix(es) applied.', warnings)
        if args.strict:
            sys.exit(1)
    else:
        logger.info('No fixes needed.')


if __name__ == '__main__':
    main()
