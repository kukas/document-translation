#!/usr/bin/env python3
"""
insert_extexts.py

For each line in the input file (an XML snippet WITHOUT any ExText elements),
insert ExText elements so that the resulting snippet matches the top-level
element sequence found in the corresponding line of the reference file.

Algorithm per line:
  1. Parse the reference line into a sequence of top-level elements.
     The reference is expected to contain ExText elements interleaved with
     "key" elements (SelectOptionCorrect*, SelectOptionIncorrect*, TypeInOption*,
     Equation*, Image*).
  2. Parse the input line into a sequence of key top-level elements plus the
     raw content (text / nested XML tokens) that lives in the spans between them.
  3. Match the ExText slots from the reference to the spans in the input:
       slot 0 – content before the first key element
       slot k – content between key element k-1 and key element k
       slot n – content after the last key element
  4. For each slot:
       - If the reference has an ExText there, wrap the span content in that
         ExText element (using the tag name from the reference).  If the span
         is empty, emit an empty self-closing <ExTextN/> element.
       - If the reference has no ExText there, the span content is emitted
         as-is (a warning is issued if the span is non-empty).
  5. The key elements are copied verbatim from the input.

Usage:
    python insert_extexts.py input.txt output.txt --reference ref.txt
    python insert_extexts.py input.txt output.txt --reference ref.txt --strict
        # exit 1 if any line was changed or any warning was emitted
"""

import re
import sys
import argparse
import logging
from typing import List, Tuple, Optional

# ---------------------------------------------------------------------------
# Tag prefix classification
# ---------------------------------------------------------------------------

EXTTEXT_PREFIX = 'ExText'
KEY_PREFIXES = (
    'SelectOptionCorrect',
    'SelectOptionIncorrect',
    'TypeInOption',
    'Equation',
    'InputOption',
    'Image',
    'Audio',
    'LineBreak',
    'CrosswordMotivationPlaceholder',
    'EmptyExText',
)
ALL_TOP_LEVEL_PREFIXES = (EXTTEXT_PREFIX,) + KEY_PREFIXES


def _top_prefix(tag_name: str) -> Optional[str]:
    for pfx in ALL_TOP_LEVEL_PREFIXES:
        if tag_name.startswith(pfx):
            return pfx
    return None


def _is_top_level(tag_name: str) -> bool:
    return _top_prefix(tag_name) is not None


def _is_extext(tag_name: str) -> bool:
    return tag_name.startswith(EXTTEXT_PREFIX)


def _is_key(tag_name: str) -> bool:
    return any(tag_name.startswith(p) for p in KEY_PREFIXES)


# ---------------------------------------------------------------------------
# Tokeniser  (kind, tag_name, raw_text)
# ---------------------------------------------------------------------------

_TOK_RE = re.compile(
    r'(<(?P<close_slash>/?)(?P<tag_name>[a-zA-Z_][a-zA-Z0-9_]*)(?P<attrs>[^>]*)>)'
    r'|([^<]+)',
    re.DOTALL,
)


def tokenise(line: str) -> List[Tuple[str, str, str]]:
    tokens = []
    for m in _TOK_RE.finditer(line):
        if m.group(1):
            tag_name = m.group('tag_name')
            attrs    = m.group('attrs')
            raw      = m.group(1)
            if m.group('close_slash'):
                tokens.append(('close', tag_name, raw))
            elif attrs.rstrip().endswith('/'):
                tokens.append(('self', tag_name, raw))
            else:
                tokens.append(('open', tag_name, raw))
        else:
            tokens.append(('text', '', m.group(0)))
    return tokens


# ---------------------------------------------------------------------------
# Parse a token list into a flat sequence of top-level items
#
# Each item is one of:
#   ('elem', tag_name, open_raw, inner_raw, close_raw)  – matched element
#   ('raw',  '',       '',        raw_text,  '')         – text / stray tag
# ---------------------------------------------------------------------------

def _parse_top_level(tokens: List[Tuple[str, str, str]]):
    """
    Greedily consume tokens, treating recognised top-level tags as containers.
    Returns a list of items (tuples as described above).
    """
    items = []
    i = 0
    while i < len(tokens):
        kind, tag_name, raw = tokens[i]
        if kind == 'self' and _is_top_level(tag_name):
            # self-closing top-level element, e.g. <Image_1/>
            items.append(('elem', tag_name, raw, '', ''))
            i += 1
            continue
        if kind == 'open' and _is_top_level(tag_name):
            # find matching close tag (accounting for same-name nesting)
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                k2, t2, _ = tokens[j]
                if k2 == 'open'  and t2 == tag_name:
                    depth += 1
                elif k2 == 'close' and t2 == tag_name:
                    depth -= 1
                j += 1
            if depth == 0:
                inner_raw = ''.join(r for _, _, r in tokens[i + 1: j - 1])
                items.append(('elem', tag_name, raw, inner_raw, tokens[j - 1][2]))
                i = j
                continue
        # anything else – raw token
        items.append(('raw', '', '', raw, ''))
        i += 1
    return items


# ---------------------------------------------------------------------------
# Parse reference line -> (extext_slots, key_seq)
#
# extext_slots[k] is the ExText tag name (e.g. 'ExText2') to use for slot k,
# or None if the reference has no ExText in that gap.
#
# key_seq is the list of key element tag names in order.
#
# There are len(key_seq)+1 slots: before key[0], between key[k] and key[k+1],
# and after key[-1].
# ---------------------------------------------------------------------------

def _parse_reference(ref_line: str):
    tokens = tokenise(ref_line)
    items  = _parse_top_level(tokens)

    key_seq: List[str] = []
    # We build extext_slots incrementally.
    # pending_extext holds the most recent ExText tag seen since the last key.
    pending_extext: Optional[str] = None
    # extext_before_next_key[i] = ExText tag name (or None) for slot i
    slots_so_far: List[Optional[str]] = []

    for item in items:
        kind, tag_name = item[0], item[1]
        if kind != 'elem':
            continue  # skip stray text/tokens at top level of reference
        if _is_extext(tag_name):
            pending_extext = tag_name
        elif _is_key(tag_name):
            slots_so_far.append(pending_extext)
            pending_extext = None
            key_seq.append(tag_name)

    # final slot (after last key)
    slots_so_far.append(pending_extext)

    return slots_so_far, key_seq


# ---------------------------------------------------------------------------
# Parse input line -> (spans, key_items)
#
# key_items[k]  = ('elem', tag_name, open_raw, inner_raw, close_raw)
# spans[k]      = raw string for the content in slot k
#
# len(spans) == len(key_items) + 1
# ---------------------------------------------------------------------------

def _parse_input(inp_line: str):
    tokens = tokenise(inp_line)
    items  = _parse_top_level(tokens)

    key_items: List = []
    spans:     List[str] = []
    current_span_parts: List[str] = []

    for item in items:
        kind, tag_name = item[0], item[1]
        if kind == 'elem' and _is_key(tag_name):
            spans.append(''.join(current_span_parts))
            current_span_parts = []
            key_items.append(item)
        elif kind == 'elem' and _is_extext(tag_name):
            # Input should not contain ExText, but handle gracefully:
            # treat its inner content as raw span content
            current_span_parts.append(item[3])  # inner_raw
        else:
            # raw token or unexpected element – add its raw text to the span
            if kind == 'raw':
                current_span_parts.append(item[3])
            else:
                # unexpected top-level element: keep verbatim
                current_span_parts.append(item[2] + item[3] + item[4])

    spans.append(''.join(current_span_parts))
    return spans, key_items


# ---------------------------------------------------------------------------
# Core: build the output line
# ---------------------------------------------------------------------------

def _is_whitespace_only(s: str) -> bool:
    return s.strip() == ''


def process_line(
    inp_line: str,
    ref_line: str,
    lineno: int,
    logger: logging.Logger,
) -> Tuple[str, bool]:
    """
    Return (output_line, changed).
    """
    extext_slots, ref_key_seq = _parse_reference(ref_line)
    spans, key_items          = _parse_input(inp_line)

    inp_key_seq = [item[1] for item in key_items]

    # --- Sanity check: key element sequences must match ---
    if inp_key_seq != ref_key_seq:
        logger.error(
            "Line %d: key element sequence mismatch – input %s vs reference %s; "
            "line written unchanged.",
            lineno, inp_key_seq, ref_key_seq,
        )
        return inp_line, False

    # --- Build output ---
    out_parts: List[str] = []

    for slot_idx, span_content in enumerate(spans):
        extext_tag = extext_slots[slot_idx]

        if extext_tag is not None:
            if _is_whitespace_only(span_content):
                # Insert an empty ExText element
                out_parts.append(f'<{extext_tag}/>')
            else:
                out_parts.append(f'<{extext_tag}>{span_content}</{extext_tag}>')
        else:
            # No ExText in reference for this slot
            if not _is_whitespace_only(span_content):
                logger.warning(
                    "Line %d slot %d: non-empty span has no ExText in reference; "
                    "content emitted bare: %r",
                    lineno, slot_idx, span_content[:80],
                )
            out_parts.append(span_content)

        # Emit the key element that follows this slot (if any)
        if slot_idx < len(key_items):
            item = key_items[slot_idx]
            # item: ('elem', tag_name, open_raw, inner_raw, close_raw)
            # self-closing elements have close_raw == '' and inner_raw == ''
            out_parts.append(item[2] + item[3] + item[4])

    output = ''.join(out_parts)
    changed = (output != inp_line)
    return output, changed


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def process_file(
    input_path: str,
    output_path: str,
    reference_path: str,
    logger: logging.Logger,
) -> Tuple[int, int]:
    """Return (changed_count, warning_count)."""

    changed_count  = 0
    warning_count  = 0

    class WarningCounter(logging.Handler):
        def emit(self, record):
            nonlocal warning_count
            if record.levelno >= logging.WARNING:
                warning_count += 1

    logger.addHandler(WarningCounter())

    with open(input_path,    'r', encoding='utf-8') as fin,  \
         open(reference_path,'r', encoding='utf-8') as fref, \
         open(output_path,   'w', encoding='utf-8') as fout:

        for lineno, (inp_raw, ref_raw) in enumerate(zip(fin, fref), start=1):
            inp_line = inp_raw.rstrip('\n')
            ref_line = ref_raw.rstrip('\n')

            out_line, changed = process_line(inp_line, ref_line, lineno, logger)
            fout.write(out_line + '\n')
            if changed:
                changed_count += 1

    return changed_count, warning_count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            'Insert ExText elements into XML snippet lines based on a reference file.\n'
            'Each line in the input is expected to contain the same key top-level '
            'elements (SelectOptionCorrect*, SelectOptionIncorrect*, TypeInOption*, '
            'Equation*, Image*) as the corresponding reference line, but without any '
            'ExText wrappers.  The script wraps the content spans between key elements '
            'in the ExText elements defined by the reference.'
        )
    )
    parser.add_argument('input_file',  help='Input file (no ExText elements)')
    parser.add_argument('output_file', help='Output file')
    parser.add_argument('--reference', required=True, metavar='FILE',
                        help='Parallel reference file containing ExText elements')
    parser.add_argument('--strict', action='store_true',
                        help='Exit with code 1 if any line was changed or any warning occurred')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show DEBUG-level messages')
    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stderr,
    )
    logger = logging.getLogger('insert_extexts')

    changed, warnings = process_file(
        args.input_file, args.output_file, args.reference, logger
    )

    logger.info('%d line(s) changed, %d warning(s).', changed, warnings)

    if args.strict and (changed or warnings):
        sys.exit(1)


if __name__ == '__main__':
    main()
