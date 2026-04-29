#!/usr/bin/env python3
"""
analyze_element_content.py

Scans XML files and reports how often each of the selected elements
('SelectOptionCorrect', 'SelectOptionIncorrect', 'TypeInOption', 'Equation')
is:
  - empty            (no children, no text)
  - text-only        (only text content, no child elements)
  - has-elements     (contains at least one child element)

Usage:
    python analyze_element_content.py file1.xml file2.xml ...
    python analyze_element_content.py /path/to/dir/         # all .xml files recursively
"""

import sys
import argparse
import collections
import pathlib
import xml.etree.ElementTree as ET


# These are treated as *prefixes*: any tag whose local name starts with one of
# these strings will be matched and counted under that prefix group.
TAG_PREFIXES_OF_INTEREST = (
    'SelectOptionCorrect',
    'SelectOptionIncorrect',
    'TypeInOption',
    'Equation',
)

# Each prefix maps to a Counter with keys: 'empty', 'text_only', 'has_elements'
Stats = dict[str, collections.Counter]


def classify_element(elem: ET.Element) -> str:
    """Classify a single element as 'empty', 'text_only', or 'has_elements'."""
    has_children = len(elem) > 0
    has_text = bool((elem.text and elem.text.strip()) or
                    any(child.tail and child.tail.strip() for child in elem))

    if has_children:
        return 'has_elements'
    elif has_text:
        return 'text_only'
    else:
        return 'empty'


def collect_stats(tag_prefix: str, root: ET.Element, stats: Stats) -> None:
    """Walk the element tree and count elements whose local name starts with tag_prefix."""
    for elem in root.iter():
        # Match by local name (strip namespace if present)
        local_name = elem.tag.split('}', 1)[-1] if '}' in elem.tag else elem.tag
        if local_name.startswith(tag_prefix):
            category = classify_element(elem)
            stats[tag_prefix][category] += 1


def process_file(path: pathlib.Path, stats: Stats) -> int:
    """
    Parse one XML file and update stats.
    Returns 0 on success, 1 on parse error.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as exc:
        # Try wrapping in a synthetic root to handle multi-root / snippet files
        try:
            text = path.read_text(encoding='utf-8')
            root = ET.fromstring(f'<_root_>{text}</_root_>')
        except ET.ParseError:
            print(f"WARNING: skipping {path}: {exc}", file=sys.stderr)
            return 1

    for tag_prefix in TAG_PREFIXES_OF_INTEREST:
        collect_stats(tag_prefix, root, stats)
    return 0


def print_report(stats: Stats) -> None:
    col_w = 22
    cat_w = 14

    header = f"{'Element prefix':<{col_w}}  {'empty':>{cat_w}}  {'text_only':>{cat_w}}  {'has_elements':>{cat_w}}  {'total':>{cat_w}}"
    print(header)
    print('-' * len(header))

    for tag in TAG_PREFIXES_OF_INTEREST:
        c = stats[tag]
        total = c['empty'] + c['text_only'] + c['has_elements']
        if total == 0:
            row = f"{tag:<{col_w}}  {'(not found)':>{cat_w * 3 + 6}}"
        else:
            def pct(n):
                return f"{n:>{cat_w - 7}} ({100*n/total:5.1f}%)"
            row = (
                f"{tag:<{col_w}}  "
                f"{pct(c['empty'])}  "
                f"{pct(c['text_only'])}  "
                f"{pct(c['has_elements'])}  "
                f"{total:>{cat_w}}"
            )
        print(row)


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Analyse how often SelectOptionCorrect, SelectOptionIncorrect, '
            'TypeInOption and Equation elements are empty, text-only, or '
            'contain child elements.'
        )
    )
    parser.add_argument(
        'paths', nargs='+',
        help='XML files or directories (directories are searched recursively for *.xml files).',
    )
    args = parser.parse_args()

    # Collect all XML file paths
    xml_files: list[pathlib.Path] = []
    for raw in args.paths:
        p = pathlib.Path(raw)
        if p.is_dir():
            xml_files.extend(sorted(p.rglob('*.xml')))
        else:
            xml_files.append(p)

    if not xml_files:
        print('No XML files found.', file=sys.stderr)
        sys.exit(1)

    stats: Stats = {tag: collections.Counter() for tag in TAG_PREFIXES_OF_INTEREST}
    error_count = 0

    for path in xml_files:
        error_count += process_file(path, stats)

    print(f"\nProcessed {len(xml_files)} file(s), {error_count} skipped due to parse errors.\n")
    print_report(stats)


if __name__ == '__main__':
    main()
