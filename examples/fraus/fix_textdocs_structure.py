#!/usr/bin/env python3
"""
fix_textdocs_structure.py

Reads a file where each line contains an XML snippet representing one or more
top-level sibling elements.  The allowed top-level tag prefixes are:
  ExText, SelectOptionCorrect, SelectOptionIncorrect, Equation

Checks two structural rules per line:
  1. No two adjacent top-level elements share the same prefix.
  2. No element whose tag-name starts with a top-level prefix is embedded
     inside a top-level element.

Fixes are applied by minimal operations:
  - Embedded top-level-prefixed elements are extracted out of their parent,
    splitting the parent into (at most) a before-part and an after-part.
  - After extraction, adjacent siblings with the same prefix are merged
    (their content is concatenated inside a single element that keeps the
    first element's full tag name, i.e. including the numeric suffix).

Usage:
    python fix_textdocs_structure.py input.txt output.txt
    python fix_textdocs_structure.py input.txt output.txt --strict
        # exit 1 if any fix was needed

The --strict flag makes the tool exit with code 1 when any line required fixing.
"""

import re
import sys
import argparse
import logging
from typing import Optional

# ---------------------------------------------------------------------------
# Tag prefixes that define top-level elements
# ---------------------------------------------------------------------------
TOP_LEVEL_PREFIXES = ('ExText', 'SelectOptionCorrect', 'SelectOptionIncorrect', 'TypeInOption', 'Equation')

# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------
# Each token is one of:
#   ('open',  tag_name, full_open_tag_text)   – <TagName ...>
#   ('close', tag_name, full_close_tag_text)  – </TagName>
#   ('self',  tag_name, full_tag_text)        – <TagName .../>
#   ('text',  '',       raw_text)             – text node (may be empty)

_TAG_RE = re.compile(
    r'</([a-zA-Z_][a-zA-Z0-9_]*)>'           # group 1 – closing tag name
    r'|<([a-zA-Z_][a-zA-Z0-9_]*)([^>]*)/>',  # group 2/3 – self-closing
    re.DOTALL,
)

_TOK_RE = re.compile(
    r'(<(?P<close_slash>/?)(?P<tag_name>[a-zA-Z_][a-zA-Z0-9_]*)(?P<attrs>[^>]*)>)'
    r'|([^<]+)',
    re.DOTALL,
)


def tokenise(line: str) -> list:
    """Return a list of (kind, tag_name, raw_text) tuples."""
    tokens = []
    for m in _TOK_RE.finditer(line):
        if m.group(1):  # an XML tag
            close_slash = m.group('close_slash')
            tag_name    = m.group('tag_name')
            attrs       = m.group('attrs')
            raw         = m.group(1)
            if close_slash:
                tokens.append(('close', tag_name, raw))
            elif attrs.rstrip().endswith('/'):
                tokens.append(('self', tag_name, raw))
            else:
                tokens.append(('open', tag_name, raw))
        else:  # text node
            tokens.append(('text', '', m.group(0)))
    return tokens


def tokens_to_str(tokens: list) -> str:
    return ''.join(raw for _, _, raw in tokens)


# ---------------------------------------------------------------------------
# Top-level prefix helpers
# ---------------------------------------------------------------------------

def top_prefix(tag_name: str) -> Optional[str]:
    """Return the top-level prefix of tag_name, or None."""
    for pfx in TOP_LEVEL_PREFIXES:
        if tag_name.startswith(pfx):
            return pfx
    return None


def is_top_level_tag(tag_name: str) -> bool:
    return top_prefix(tag_name) is not None


# ---------------------------------------------------------------------------
# Parse a flat token list into a list of top-level Element nodes
# ---------------------------------------------------------------------------

class Element:
    """Represents a single top-level element with its children tokens."""

    def __init__(self, open_tok, children: list, close_tok):
        # open_tok  = ('open',  tag_name, raw)
        # children  = list of tokens or Element objects (mixed)
        # close_tok = ('close', tag_name, raw)
        self.open_tok  = open_tok
        self.children  = children   # list of (kind, tag_name, raw) or Element
        self.close_tok = close_tok

    @property
    def tag_name(self) -> str:
        return self.open_tok[1]

    @property
    def prefix(self) -> str:
        return top_prefix(self.tag_name) or self.tag_name

    def to_str(self) -> str:
        inner = ''.join(
            c.to_str() if isinstance(c, Element) else c[2]
            for c in self.children
        )
        return self.open_tok[2] + inner + self.close_tok[2]


def parse_top_level(tokens: list) -> list:
    """
    Parse flat tokens into a list of top-level items.
    Each item is either an Element (for a matched open/close pair) or a raw
    token tuple (for text nodes or unmatched tags).

    Only top-level-prefixed elements are treated as top-level containers here;
    everything else is treated as a raw token at this stage.
    """
    result = []
    i = 0
    while i < len(tokens):
        kind, tag_name, raw = tokens[i]
        if kind == 'open' and is_top_level_tag(tag_name):
            # find the matching close tag (same tag name, accounting for nesting)
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                k2, t2, _ = tokens[j]
                if k2 == 'open' and t2 == tag_name:
                    depth += 1
                elif k2 == 'close' and t2 == tag_name:
                    depth -= 1
                j += 1
            if depth == 0:
                close_tok = tokens[j - 1]
                children = tokens[i + 1: j - 1]
                result.append(Element(tokens[i], children, close_tok))
                i = j
            else:
                # Unmatched open tag – treat as raw token
                result.append(tokens[i])
                i += 1
        else:
            result.append(tokens[i])
            i += 1
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def find_embedded_top_level(element: Element) -> Optional[int]:
    """
    Return the index (within element.children) of the first child token that
    opens a top-level-prefixed element (directly inside element, regardless of
    depth).  Returns None if the element is clean.

    We walk the children list looking for an ('open', top_tag, ...) token
    that is not itself nested inside a non-top-level open/close pair.
    (Top-level-prefixed elements cannot nest inside each other in valid input,
    so any occurrence is a violation.)
    """
    # Flatten children tokens recursively to find any top-level tag inside.
    # We only need the *first* one for fixing (we fix iteratively).
    depth = 0  # depth of non-top-level nesting
    for idx, child in enumerate(element.children):
        if isinstance(child, Element):
            # This should not happen in the initial parse, but handle defensively
            continue
        kind, tag_name, raw = child
        if kind == 'open':
            if is_top_level_tag(tag_name):
                return idx
            else:
                depth += 1
        elif kind == 'close':
            depth -= 1
    return None


def validate_line(items: list) -> list:
    """
    Return a list of violation descriptions (strings) for the parsed item list.
    Empty list means the line is valid.
    """
    violations = []

    # Rule 1: adjacent same-prefix top-level elements
    # Rule 3: bare non-whitespace text at top level
    prev_prefix = None
    for item in items:
        if isinstance(item, Element):
            pfx = item.prefix
            if pfx == prev_prefix:
                violations.append(
                    f"Adjacent top-level elements with same prefix '{pfx}'"
                )
            prev_prefix = pfx
        else:
            kind, tag_name, raw = item
            if kind == 'text' and raw.strip():
                violations.append(f"Top-level text node: {raw!r}")
            prev_prefix = None  # text / other tag between elements resets

    # Rule 2: embedded top-level-prefixed elements
    for item in items:
        if isinstance(item, Element):
            idx = find_embedded_top_level(item)
            if idx is not None:
                inner_tag = item.children[idx][1]
                violations.append(
                    f"Element <{inner_tag}> embedded inside <{item.tag_name}>"
                )

    return violations


# ---------------------------------------------------------------------------
# Fixing
# ---------------------------------------------------------------------------

def extract_embedded(element: Element, embed_idx: int, next_same_prefix: 'Element | None' = None) -> list:
    """
    Given an Element and the index of an embedded top-level open tag inside
    its children list, extract that embedded element out, returning a list of
    replacement items:

        [before_element?, embedded_element, after_element?]

    where before_element / after_element are new Element objects that hold
    the content of the original element that appeared before / after the
    embedded element.  Either may be absent if there is no content on that side.

    If *next_same_prefix* is provided and the "after" part would be adjacent to
    it (same prefix), the after element reuses next_same_prefix's tag name so
    that the two can be cleanly merged in one step.

    The embedded element itself may be self-closing or a matched open/close pair
    within the children.
    """
    children = element.children
    embed_kind, embed_tag, embed_raw = children[embed_idx]

    # Find the matching close tag for the embedded element
    depth = 1
    j = embed_idx + 1
    while j < len(children) and depth > 0:
        k2, t2, _ = children[j]
        if k2 == 'open' and t2 == embed_tag:
            depth += 1
        elif k2 == 'close' and t2 == embed_tag:
            depth -= 1
        j += 1

    if depth == 0:
        embed_close_tok = children[j - 1]
        embed_children  = children[embed_idx + 1: j - 1]
        before_children = children[:embed_idx]
        after_children  = children[j:]
        embedded = Element(children[embed_idx], embed_children, embed_close_tok)
    else:
        # Self-closing or unmatched – treat the single token as embedded
        before_children = children[:embed_idx]
        after_children  = children[embed_idx + 1:]
        embedded = children[embed_idx]  # raw token

    result = []

    # Before part – keep parent's open/close tags
    before_content = ''.join(
        c.to_str() if isinstance(c, Element) else c[2] for c in before_children
    )
    if before_content:
        before_elem = Element(element.open_tok, list(before_children), element.close_tok)
        result.append(before_elem)

    # The extracted embedded element / token
    result.append(embedded)

    # After part:
    # If the after content is non-empty, wrap it in an element.
    # Prefer the tag name of the immediately following same-prefix sibling so
    # that they merge into one correctly-named element.
    after_content = ''.join(
        c.to_str() if isinstance(c, Element) else c[2] for c in after_children
    )
    if after_content:
        if next_same_prefix is not None:
            # Borrow the tag name from the following sibling; the two will merge.
            after_open_raw  = next_same_prefix.open_tok[2]
            after_close_raw = next_same_prefix.close_tok[2]
            after_tag       = next_same_prefix.tag_name
        else:
            after_open_raw  = element.open_tok[2]
            after_close_raw = element.close_tok[2]
            after_tag       = element.tag_name
        after_open_tok  = ('open',  after_tag, after_open_raw)
        after_close_tok = ('close', after_tag, after_close_raw)
        after_elem = Element(after_open_tok, list(after_children), after_close_tok)
        result.append(after_elem)

    return result


def merge_adjacent_same_prefix(items: list) -> list:
    """
    Merge adjacent Element items that share the same top-level prefix.
    The merged element keeps the open tag of the first and the close tag of
    the last; intermediate open/close tags are converted to plain text nodes
    so that no content is lost. Actually we just concatenate their inner
    content and wrap in the first element's open/close tags.
    """
    if not items:
        return items

    result = []
    i = 0
    while i < len(items):
        item = items[i]
        if not isinstance(item, Element):
            result.append(item)
            i += 1
            continue

        pfx = item.prefix
        # Collect a run of Elements with the same prefix
        run = [item]
        j = i + 1
        while j < len(items) and isinstance(items[j], Element) and items[j].prefix == pfx:
            run.append(items[j])
            j += 1

        if len(run) == 1:
            result.append(item)
        else:
            # Merge: concatenate inner children, keep first open tag and
            # reconstruct a matching close tag (same tag name as the open tag).
            merged_children = []
            for elem in run:
                merged_children.extend(elem.children)
            open_tok  = run[0].open_tok   # ('open', tag_name, raw)
            tag_name  = open_tok[1]
            close_raw = f'</{tag_name}>'
            close_tok = ('close', tag_name, close_raw)
            merged = Element(open_tok, merged_children, close_tok)
            result.append(merged)

        i = j

    return result


def absorb_toplevel_text(items: list, lineno: int, logger: logging.Logger) -> tuple:
    """
    Absorb bare non-whitespace text nodes at the top level into the nearest
    adjacent top-level Element.  Prefer the immediately preceding element;
    fall back to the immediately following one.  Pure-whitespace text tokens
    are silently dropped.

    Returns (new_items, changed).
    """
    changed = False

    # Work in passes until stable (a single pass is usually enough).
    for _safety in range(200):
        new_items = list(items)
        pass_changed = False
        i = 0
        while i < len(new_items):
            item = new_items[i]
            if isinstance(item, Element):
                i += 1
                continue
            kind, tag_name, raw = item
            if kind != 'text':
                i += 1
                continue
            if not raw.strip():
                # Pure whitespace – drop silently
                new_items.pop(i)
                pass_changed = True
                changed = True
                continue  # re-examine same index
            # Non-whitespace bare text: find nearest adjacent Element
            # Look backward for the closest preceding Element
            prev_elem_idx = None
            for j in range(i - 1, -1, -1):
                if isinstance(new_items[j], Element):
                    prev_elem_idx = j
                    break
            # Look forward for the closest following Element
            next_elem_idx = None
            for j in range(i + 1, len(new_items)):
                if isinstance(new_items[j], Element):
                    next_elem_idx = j
                    break

            if prev_elem_idx is not None:
                target = new_items[prev_elem_idx]
                logger.warning(
                    "Line %d: top-level text %r absorbed into preceding <%s>.",
                    lineno, raw, target.tag_name,
                )
                # Append the text token to the end of the target's children
                target.children.append(('text', '', raw))
                new_items.pop(i)
                pass_changed = True
                changed = True
                # Don't advance i – the next item is now at the same index
            elif next_elem_idx is not None:
                target = new_items[next_elem_idx]
                logger.warning(
                    "Line %d: top-level text %r absorbed into following <%s>.",
                    lineno, raw, target.tag_name,
                )
                # Prepend the text token at the start of the target's children
                target.children.insert(0, ('text', '', raw))
                new_items.pop(i)
                pass_changed = True
                changed = True
            else:
                logger.error(
                    "Line %d: top-level text %r has no adjacent element to "
                    "absorb into – left unchanged.",
                    lineno, raw,
                )
                i += 1

        items = new_items
        if not pass_changed:
            break

    return items, changed


def fix_items(items: list, lineno: int, logger: logging.Logger) -> tuple:
    """
    Repeatedly fix violations until none remain (or a safety limit is hit).
    Returns (fixed_items, was_changed).
    """
    changed_total = False

    # --- Fix rule 3: bare top-level text nodes ---
    items, changed3 = absorb_toplevel_text(items, lineno, logger)
    if changed3:
        changed_total = True

    for _safety in range(200):
        # --- Fix rule 2: embedded top-level tags ---
        new_items = []
        changed_pass = False
        for pos, item in enumerate(items):
            if isinstance(item, Element):
                idx = find_embedded_top_level(item)
                if idx is not None:
                    inner_tag = item.children[idx][1]
                    logger.warning(
                        "Line %d: <%-20s> embedded inside <%s> – extracting.",
                        lineno, inner_tag, item.tag_name,
                    )
                    # Find the immediately following Element with the same prefix
                    next_same = None
                    for nxt in items[pos + 1:]:
                        if isinstance(nxt, Element):
                            if nxt.prefix == item.prefix:
                                next_same = nxt
                            break  # stop at first Element regardless
                    replacement = extract_embedded(item, idx, next_same)
                    new_items.extend(replacement)
                    changed_pass = True
                    changed_total = True
                    continue
            new_items.append(item)
        items = new_items

        # --- Fix rule 1: adjacent same-prefix elements ---
        merged = merge_adjacent_same_prefix(items)
        if len(merged) != len(items) or any(
            (isinstance(a, Element) and isinstance(b, Element) and a.tag_name != b.tag_name)
            for a, b in zip(merged, items)
            if isinstance(a, Element)
        ):
            if merged != items:
                logger.warning(
                    "Line %d: merging adjacent same-prefix top-level elements.",
                    lineno,
                )
                changed_pass = True
                changed_total = True
        items = merged

        if not changed_pass:
            break

    return items, changed_total


def items_to_str(items: list) -> str:
    return ''.join(item.to_str() if isinstance(item, Element) else item[2] for item in items)


def _top_level_elements(items: list) -> list:
    """Return only the Element objects from a parsed item list."""
    return [it for it in items if isinstance(it, Element)]


def rename_to_reference(items: list, ref_items: list, lineno: int, logger: logging.Logger) -> tuple:
    """
    Rename top-level elements in *items* so that their tag names match the
    corresponding elements in *ref_items* (matched by position).

    If the counts differ, as many elements as possible are renamed and a
    warning is emitted.  Returns (new_items, was_changed).
    """
    elems     = _top_level_elements(items)
    ref_elems = _top_level_elements(ref_items)

    if not ref_elems:
        return items, False

    if len(elems) != len(ref_elems):
        logger.warning(
            "Line %d: element count mismatch – input has %d top-level element(s), "
            "reference has %d; renaming up to min(%d, %d).",
            lineno, len(elems), len(ref_elems), len(elems), len(ref_elems),
        )

    changed = False
    for elem, ref_elem in zip(elems, ref_elems):
        new_name = ref_elem.tag_name
        if elem.tag_name == new_name:
            continue
        logger.debug(
            "Line %d: renaming <%s> → <%s> to match reference.",
            lineno, elem.tag_name, new_name,
        )
        # Patch the open token
        old_open_raw  = elem.open_tok[2]
        new_open_raw  = re.sub(
            r'^<[a-zA-Z_][a-zA-Z0-9_]*', '<' + new_name, old_open_raw, count=1
        )
        elem.open_tok  = ('open',  new_name, new_open_raw)
        # Patch the close token
        elem.close_tok = ('close', new_name, f'</{new_name}>')
        changed = True

    return items, changed


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_line(
    line: str,
    lineno: int,
    logger: logging.Logger,
    ref_line: 'str | None' = None,
) -> tuple:
    """
    Process one line.  Returns (output_line, was_changed).
    """
    tokens = tokenise(line)
    items  = parse_top_level(tokens)

    violations = validate_line(items)
    if not violations:
        # Still apply reference renaming even when structure is already valid
        if ref_line is not None:
            ref_tokens = tokenise(ref_line)
            ref_items  = parse_top_level(ref_tokens)
            items, renamed = rename_to_reference(items, ref_items, lineno, logger)
            if renamed:
                return items_to_str(items), True
        return line, False

    for v in violations:
        logger.debug("Line %d: violation detected: %s", lineno, v)

    fixed_items, changed = fix_items(items, lineno, logger)

    # Rename to match reference structure (if provided)
    if ref_line is not None:
        ref_tokens = tokenise(ref_line)
        ref_items  = parse_top_level(ref_tokens)
        fixed_items, renamed = rename_to_reference(fixed_items, ref_items, lineno, logger)
        changed = changed or renamed

    # Final validation check
    remaining = validate_line(fixed_items)
    if remaining:
        for v in remaining:
            logger.error(
                "Line %d: could not fix violation: %s", lineno, v
            )

    return items_to_str(fixed_items), changed


def process_file(
    input_path: str,
    output_path: str,
    logger: logging.Logger,
    reference_path: 'str | None' = None,
) -> tuple:
    """
    Process the whole file.  Returns (fix_count, error_count).
    """
    fix_count   = 0
    error_count = 0

    class ErrorCounter(logging.Handler):
        def emit(self, record):
            nonlocal error_count
            if record.levelno >= logging.ERROR:
                error_count += 1

    logger.addHandler(ErrorCounter())

    ref_lines = None
    if reference_path is not None:
        with open(reference_path, 'r', encoding='utf-8') as fref:
            ref_lines = [l.rstrip('\n') for l in fref]

    with open(input_path, 'r', encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8') as fout:
        for lineno, raw_line in enumerate(fin, start=1):
            line    = raw_line.rstrip('\n')
            ref_line = ref_lines[lineno - 1] if (ref_lines is not None and lineno - 1 < len(ref_lines)) else None
            fixed_line, changed = process_line(line, lineno, logger, ref_line=ref_line)
            fout.write(fixed_line + '\n')
            if changed:
                fix_count += 1

    return fix_count, error_count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            'Verify and fix structural rules in textdoc snippet files.\n'
            'Each line must consist of sibling top-level elements '
            '(ExText*, SelectOptionCorrect*, SelectOptionIncorrect*, Equation*) '
            'with no adjacent elements sharing the same prefix, and no '
            'top-level-prefixed elements embedded inside a top-level element.'
        )
    )
    parser.add_argument('input_file',  help='Input file path')
    parser.add_argument('output_file', nargs='?', default=None, help='Output file path (not required with --verify-only)')
    parser.add_argument(
        '--strict', action='store_true',
        help='Exit with code 1 if any fix was applied or any error occurred.',
    )
    parser.add_argument(
        '--verify-only', action='store_true',
        help=(
            'Only report violations; do not write output_file. '
            'Exits with code 1 if any violation is found.'
        ),
    )
    parser.add_argument(
        '--reference', metavar='FILE',
        help=(
            'Parallel reference file (e.g. the source .textdocs.txt). '
            'Each line\'s top-level element names are used to rename the '
            'corresponding output line\'s top-level elements after fixing.'
        ),
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Show DEBUG-level messages (individual violation details).',
    )
    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stderr,
    )
    logger = logging.getLogger('fix_textdocs_structure')

    if not args.verify_only and args.output_file is None:
        parser.error('output_file is required unless --verify-only is specified.')

    if args.verify_only:
        # Just scan and report, no output file
        violation_count = 0
        with open(args.input_file, 'r', encoding='utf-8') as fin:
            for lineno, raw_line in enumerate(fin, start=1):
                line   = raw_line.rstrip('\n')
                tokens = tokenise(line)
                items  = parse_top_level(tokens)
                viols  = validate_line(items)
                for v in viols:
                    logger.warning("Line %d: %s", lineno, v)
                    violation_count += 1
        if violation_count:
            logger.info('%d violation(s) found.', violation_count)
            sys.exit(1)
        else:
            logger.info('No violations found.')
        return

    fix_count, error_count = process_file(args.input_file, args.output_file, logger, reference_path=args.reference)

    if fix_count or error_count:
        logger.info(
            '%d line(s) fixed, %d error(s) encountered.',
            fix_count, error_count,
        )
        if args.strict:
            sys.exit(1)
    else:
        logger.info('No fixes needed.')


if __name__ == '__main__':
    main()
