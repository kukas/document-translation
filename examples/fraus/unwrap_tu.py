#!/usr/bin/env python3
"""Extract text content from <tu> elements in a simple XML file, one line per element.
An empty <tu/> or <tu></tu> is written as an empty line.
"""
import sys
import xml.etree.ElementTree as ET

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.xml> <output.txt>", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(sys.argv[1])
    root = tree.getroot()

    with open(sys.argv[2], "w", encoding="utf-8") as out:
        for tu in root.iter("tu"):
            out.write((tu.text or "") + "\n")

if __name__ == "__main__":
    main()
