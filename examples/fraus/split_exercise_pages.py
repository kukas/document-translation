#!/usr/bin/env python3
"""
Split a Fraus XML file into multiple files, one per ExercisePages element.

Usage:
    python split_exercise_pages.py <input.xml> [output_dir]

Output files are named <basename>-01.xml, <basename>-02.xml, etc.
If output_dir is not given, files are written next to the input file.
"""

import sys
import os
import copy
from lxml import etree


def split_exercise_pages(input_path: str, output_dir: str | None = None) -> list[str]:
    """Split XML file by /DOC/ExercisePages elements.

    Returns a list of output file paths that were written.
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_path))

    os.makedirs(output_dir, exist_ok=True)

    basename = os.path.splitext(os.path.basename(input_path))[0]

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(input_path, parser)
    root = tree.getroot()

    exercise_pages = root.findall("ExercisePages")
    if not exercise_pages:
        print(f"No ExercisePages elements found in {input_path}", file=sys.stderr)
        return []

    print(f"Found {len(exercise_pages)} ExercisePages element(s) in {input_path}")

    output_paths = []
    for i, ep in enumerate(exercise_pages, start=1):
        # Build a new root element with the same tag and namespaces as the original
        new_root = copy.deepcopy(root)

        # Remove all ExercisePages children from the copy, then add just this one
        for existing_ep in new_root.findall("ExercisePages"):
            new_root.remove(existing_ep)

        new_root.append(copy.deepcopy(ep))

        new_tree = etree.ElementTree(new_root)
        out_filename = f"{basename}-{i:02d}.xml"
        out_path = os.path.join(output_dir, out_filename)

        new_tree.write(
            out_path,
            xml_declaration=True,
            encoding="utf-8",
            pretty_print=True,
        )
        print(f"  Written: {out_path}")
        output_paths.append(out_path)

    return output_paths


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(input_path):
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    split_exercise_pages(input_path, output_dir)


if __name__ == "__main__":
    main()
