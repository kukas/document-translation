import logging
from typing import Dict, List, Tuple
import argparse

from document_translation.markuptranslator import Translator

logger = logging.getLogger(__name__)


class TMTranslator(Translator):
    """A translator backed by a translation memory loaded from two line-by-line aligned files.

    For every source string passed to :meth:`translate`, the TM is looked up
    and the corresponding target string is returned.  If a source string is not
    found in the TM a warning is logged and the source string is returned
    unchanged as a fallback.
    """

    def __init__(self, src_file: str, tgt_file: str) -> None:
        """Load the translation memory from *src_file* and *tgt_file*.

        Both files must have the same number of lines; each line *i* in
        *src_file* is the source counterpart of line *i* in *tgt_file*.

        Args:
            src_file: Path to the file containing source sentences (one per line).
            tgt_file: Path to the file containing target sentences (one per line).
        """
        self.tm: Dict[str, str] = {}
        with open(src_file, encoding="utf-8") as f_src, \
             open(tgt_file, encoding="utf-8") as f_tgt:
            for lineno, (src_line, tgt_line) in enumerate(zip(f_src, f_tgt), start=1):
                src = src_line.rstrip("\n")
                tgt = tgt_line.rstrip("\n")
                if src in self.tm and self.tm[src] != tgt:
                    logger.warning(
                        "Duplicate source entry at line %d (keeping first occurrence): %r",
                        lineno, src,
                    )
                else:
                    self.tm[src] = tgt
        logger.info("Loaded %d translation memory entries from %r / %r", len(self.tm), src_file, tgt_file)

    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        """Translate *input_text* using the translation memory.

        The input is split into lines.  Each line is looked up in the TM.
        Lines that are not found are returned unchanged and a warning is logged.

        Returns:
            A tuple ``(src_sentences, tgt_sentences)`` where each element is a
            list of strings with a trailing space (or ``\\n`` for line-ending
            sentences), matching the convention used by :class:`LindatTranslator`.
        """
        if input_text == "":
            return [], []

        ends_with_newline = input_text.endswith("\n")
        lines = input_text.splitlines()

        src_sentences: List[str] = []
        tgt_sentences: List[str] = []

        for i, line in enumerate(lines):
            is_last = i == len(lines) - 1
            # Determine the suffix: newline for every line except possibly the last
            suffix = "\n" if (not is_last or ends_with_newline) else ""

            if line in self.tm:
                tgt = self.tm[line]
            else:
                logger.warning("Source string not found in translation memory: %r", line)
                tgt = line

            src_sentences.append(line + suffix)
            tgt_sentences.append(tgt + suffix)

        return src_sentences, tgt_sentences


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="Translate a text file using a translation memory")
    parser.add_argument("input_file", help="Input text file")
    parser.add_argument("src_tm_file", help="Translation memory source file (one sentence per line)")
    parser.add_argument("tgt_tm_file", help="Translation memory target file (one sentence per line)")
    args = parser.parse_args()

    translator = TMTranslator(args.src_tm_file, args.tgt_tm_file)

    with open(args.input_file, encoding="utf-8") as f_in:
        source = f_in.read()
        src_sentences, tgt_sentences = translator.translate(source)
        print("".join(tgt_sentences), end="")
