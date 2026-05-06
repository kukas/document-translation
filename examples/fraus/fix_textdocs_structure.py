#!/usr/bin/env python3
"""Lift embedded selected element types so they are never nested."""

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import List, Tuple


OPTION_PREFIXES = ("SelectOptionCorrect", "SelectOptionIncorrect", "TypeInOption")
TAG_RE = re.compile(r"<[^>]+>|[^<]+", re.DOTALL)
NAME_RE = re.compile(r"^<\s*/?\s*([A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class Node:
    tag: str
    open_raw: str
    close_raw: str = ""
    children: List["Token"] = field(default_factory=list)

    def to_str(self) -> str:
        inner = "".join(token_to_str(child) for child in self.children)
        return f"{self.open_raw}{inner}{self.close_raw}"


Token = Tuple[str, str] | Node


def token_to_str(token: Token) -> str:
    if isinstance(token, Node):
        return token.to_str()
    return token[1]


def is_option_tag(tag: str) -> bool:
    return any(tag.startswith(prefix) for prefix in OPTION_PREFIXES)


def tokenize_xmlish(text: str) -> List[Tuple[str, str, str]]:
    out = []
    for chunk in TAG_RE.findall(text):
        if not chunk.startswith("<"):
            out.append(("text", "", chunk))
            continue

        name_match = NAME_RE.match(chunk)
        if not name_match:
            out.append(("text", "", chunk))
            continue

        tag = name_match.group(1)
        stripped = chunk.strip()
        if stripped.startswith("</"):
            out.append(("close", tag, chunk))
        elif stripped.endswith("/>"):
            out.append(("self", tag, chunk))
        else:
            out.append(("open", tag, chunk))
    return out


def parse_tokens(tokens: List[Tuple[str, str, str]]) -> List[Token]:
    root = Node("__ROOT__", "")
    stack: List[Node] = [root]

    for kind, tag, raw in tokens:
        parent = stack[-1]
        if kind == "text":
            parent.children.append(("text", raw))
        elif kind == "self":
            parent.children.append(Node(tag, raw, ""))
        elif kind == "open":
            node = Node(tag, raw)
            parent.children.append(node)
            stack.append(node)
        elif kind == "close":
            if len(stack) > 1 and stack[-1].tag == tag:
                stack[-1].close_raw = raw
                stack.pop()
            else:
                parent.children.append(("text", raw))

    # If parsing is unbalanced, keep original text untouched.
    if len(stack) != 1:
        raise ValueError("Unbalanced tags")

    return root.children


def lift_embedded_options(nodes: List[Token]) -> Tuple[List[Token], List[Token]]:
    kept: List[Token] = []
    lifted: List[Token] = []

    for token in nodes:
        if not isinstance(token, Node):
            kept.append(token)
            continue

        child_kept, child_lifted = lift_embedded_options(token.children)
        token.children = child_kept

        if is_option_tag(token.tag):
            lifted.append(token)
            lifted.extend(child_lifted)
        else:
            kept.append(token)
            kept.extend(child_lifted)

    return kept, lifted


def process_line(line: str) -> Tuple[str, bool]:
    tokens = tokenize_xmlish(line)
    parsed = parse_tokens(tokens)

    output: List[Token] = []
    changed = False

    for token in parsed:
        if not isinstance(token, Node):
            output.append(token)
            continue

        child_kept, child_lifted = lift_embedded_options(token.children)
        if child_lifted:
            changed = True
        token.children = child_kept

        output.append(token)
        output.extend(child_lifted)

    return "".join(token_to_str(t) for t in output), changed


def process_file(input_path: str, output_path: str, logger: logging.Logger) -> int:
    fixed = 0
    with open(input_path, "r", encoding="utf-8") as fin, open(
        output_path, "w", encoding="utf-8"
    ) as fout:
        for lineno, raw_line in enumerate(fin, start=1):
            line = raw_line.rstrip("\n")
            try:
                new_line, changed = process_line(line)
            except Exception:
                # Keep original line if parsing fails.
                new_line, changed = line, False

            fout.write(new_line + "\n")
            if changed:
                fixed += 1
                logger.info("Line %s: fixed", lineno)
    return fixed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix embedded selected element types (never allow nesting)."
    )
    parser.add_argument("input_file", help="Input file path")
    parser.add_argument("output_file", help="Output file path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any line changed",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stderr,
    )
    logger = logging.getLogger("fix_textdocs_structure_new")

    fixed = process_file(args.input_file, args.output_file, logger)
    logger.info("%s line(s) fixed", fixed)

    if args.strict and fixed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
