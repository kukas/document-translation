#!/usr/bin/env python3
"""
Replace the `.content[].text` values in a Textdocs JSONL file with lines from a text file.

Usage:
    python3 replace_textdocs_texts.py <translations.txt> < textdocs.jsonl > output.jsonl

The script reads Textdocs JSONL (one JSON object per line) from stdin, reads replacement
lines from the positional text file argument, and writes the updated JSONL to stdout.
The replacement lines are consumed sequentially across all textdocs. If the total number
of replacement lines does not match the total number of content items across all textdocs,
a warning is emitted.
"""

import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replace .content[].text values in a Textdocs JSONL with lines from a file."
    )
    parser.add_argument(
        "translations",
        type=str,
        help="Path to the file with replacement text lines (one per content item, across all textdocs).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.translations, "r", encoding="utf-8") as f:
        replacement_lines = [line.rstrip("\n") for line in f]

    repl_iter = iter(replacement_lines)
    n_content_total = 0

    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line:
            continue
        textdoc = json.loads(line)
        content = textdoc.get("content", [])
        n_content_total += len(content)
        for item in content:
            item["text"] = next(repl_iter, item["text"])
        sys.stdout.write(json.dumps(textdoc, ensure_ascii=False) + "\n")

    n_replacements = len(replacement_lines)
    if n_replacements != n_content_total:
        logger.warning(
            f"Line count mismatch: {n_content_total} content item(s) across all textdocs "
            f"but {n_replacements} replacement line(s) provided."
        )


if __name__ == "__main__":
    main()
