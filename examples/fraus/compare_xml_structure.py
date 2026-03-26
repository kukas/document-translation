#!/usr/bin/env python3
"""
compare_xml_structure.py

Check whether two XML files are structurally identical:
  - same element tree (tag names, nesting, order)
  - same attributes and attribute values on every element
  - text content (element.text / element.tail) MAY differ

Exits 0 if the structures match, 1 if they differ or an error occurs.

Usage:
    python compare_xml_structure.py file_a.xml file_b.xml
    python compare_xml_structure.py file_a.xml file_b.xml --skip-xml-declaration
    python compare_xml_structure.py file_a.xml file_b.xml --verbose
"""

import sys
import argparse
import logging
import xml.etree.ElementTree as ET


def load(path: str, skip_decl: bool) -> ET.Element:
    with open(path, "r", encoding="utf-8") as fh:
        if skip_decl:
            fh.readline()          # drop <?xml … ?>
        return ET.parse(fh).getroot()


def _elem_path(path: list) -> str:
    """Human-readable XPath-like location from a stack of (tag, index) pairs."""
    return "/" + "/".join(f"{tag}[{idx}]" for tag, idx in path)


def compare(
    a: ET.Element,
    b: ET.Element,
    path: list,
    logger: logging.Logger,
) -> bool:
    """
    Recursively compare element *a* from file A with element *b* from file B.
    Returns True if structures match, False if any difference is found.
    Continues walking even after the first mismatch to report all differences.
    """
    location = _elem_path(path)
    ok = True

    # 1. Tag name
    if a.tag != b.tag:
        logger.error("%s  tag mismatch: %r vs %r", location, a.tag, b.tag)
        ok = False

    # 2. Attributes (both keys and values)
    if a.attrib != b.attrib:
        only_a = {k: v for k, v in a.attrib.items() if k not in b.attrib}
        only_b = {k: v for k, v in b.attrib.items() if k not in a.attrib}
        diff   = {k: (a.attrib[k], b.attrib[k])
                  for k in a.attrib
                  if k in b.attrib and a.attrib[k] != b.attrib[k]}
        if only_a:
            logger.error("%s  attributes only in A: %s", location, only_a)
        if only_b:
            logger.error("%s  attributes only in B: %s", location, only_b)
        for k, (va, vb) in diff.items():
            logger.error("%s  attribute %r differs: %r vs %r", location, k, va, vb)
        ok = False

    # 3. Number of children
    children_a = list(a)
    children_b = list(b)
    if len(children_a) != len(children_b):
        logger.error(
            "%s  child count mismatch: %d vs %d",
            location, len(children_a), len(children_b),
        )
        ok = False
        # Still recurse over the common prefix so we surface nested differences
        pairs = zip(children_a, children_b)
    else:
        pairs = zip(children_a, children_b)

    # 4. Recurse into children
    tag_counters: dict[str, int] = {}
    for ca, cb in pairs:
        tag_counters[ca.tag] = tag_counters.get(ca.tag, 0) + 1
        child_path = path + [(ca.tag, tag_counters[ca.tag])]
        if not compare(ca, cb, child_path, logger):
            ok = False

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check structural identity of two XML files (text may differ)."
    )
    parser.add_argument("file_a", help="First XML file")
    parser.add_argument("file_b", help="Second XML file")
    parser.add_argument(
        "--skip-xml-declaration",
        action="store_true",
        help="Skip the first line (<?xml …?>) before parsing – "
             "useful for FRAUS files declared as utf-16 but actually utf-8",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Also log a confirmation when structures match",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.DEBUG,
        stream=sys.stderr,
    )
    logger = logging.getLogger("compare_xml_structure")

    # --- load ---
    try:
        root_a = load(args.file_a, args.skip_xml_declaration)
    except Exception as exc:
        logger.error("Cannot parse %s: %s", args.file_a, exc)
        sys.exit(1)

    try:
        root_b = load(args.file_b, args.skip_xml_declaration)
    except Exception as exc:
        logger.error("Cannot parse %s: %s", args.file_b, exc)
        sys.exit(1)

    # --- compare ---
    root_tag_a = root_a.tag
    root_tag_b = root_b.tag
    ok = compare(root_a, root_b, [(root_tag_a, 1)], logger)

    if ok:
        if args.verbose:
            logger.info("OK – structures are identical.")
        sys.exit(0)
    else:
        logger.warning("Structures differ (see errors above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
