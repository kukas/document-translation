import logging
import re
from typing import Dict, List, Optional, Tuple
import argparse

from sentence_splitter import SentenceSplitter  # type: ignore

from document_translation.markuptranslator import Translator

logger = logging.getLogger(__name__)

SENT_LEN_LIMIT = 500


def _normalize_ws(text: str) -> str:
    """Collapse every run of whitespace to a single space, and strip."""
    return re.sub(r'\s+', ' ', text).strip()


class TMTranslator(Translator):
    """A translator backed by a translation memory loaded from two line-by-line aligned files.

    For every source string passed to :meth:`translate`, the TM is looked up
    and the corresponding target string is returned.  If a source string is not
    found in the local TM, the global TM (if provided) is tried next.  If it
    is not found in either, a warning is logged and the source string is returned
    unchanged as a fallback.
    """

    def __init__(self, src_file: str, tgt_file: str, src_lang: str,
                 global_src_file: str = None, global_tgt_file: str = None,
                 fallback_translator: Optional["Translator"] = None) -> None:
        """Load the translation memory from *src_file* and *tgt_file*.

        Both files must have the same number of lines; each line *i* in
        *src_file* is the source counterpart of line *i* in *tgt_file*.

        Args:
            src_file: Path to the file containing source sentences (one per line).
            tgt_file: Path to the file containing target sentences (one per line).
            src_lang: BCP-47 language code of the source language (used by the
                sentence splitter, e.g. ``"de"`` or ``"uk"``).
            global_src_file: Optional path to the global TM source file.
            global_tgt_file: Optional path to the global TM target file.
            fallback_translator: Optional :class:`Translator` (e.g.
                :class:`~document_translation.lindat_services.translate.LindatTranslator`)
                used when a sentence is not found in any TM.  Only sentences
                that contain at least one alphabetical character are sent to the
                fallback; others are kept as-is.
        """
        self.splitter = SentenceSplitter(language=src_lang)
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

        # Build a normalized-whitespace index for fuzzy local lookups.
        # Maps normalized_src -> (original_src, tgt).  Only the first
        # occurrence of each normalized key is kept (consistent with self.tm).
        self.tm_norm: Dict[str, Tuple[str, str]] = {}
        for src, tgt in self.tm.items():
            key = _normalize_ws(src)
            if key not in self.tm_norm:
                self.tm_norm[key] = (src, tgt)

        self.global_tm: Dict[str, str] = {}
        if global_src_file and global_tgt_file:
            with open(global_src_file, encoding="utf-8") as f_src, \
                 open(global_tgt_file, encoding="utf-8") as f_tgt:
                for lineno, (src_line, tgt_line) in enumerate(zip(f_src, f_tgt), start=1):
                    src = src_line.rstrip("\n")
                    tgt = tgt_line.rstrip("\n")
                    if src in self.global_tm and self.global_tm[src] != tgt:
                        logger.warning(
                            "Duplicate source entry at line %d in global TM (keeping first occurrence): %r",
                            lineno, src,
                        )
                    else:
                        self.global_tm[src] = tgt
            logger.info("Loaded %d global translation memory entries from %r / %r",
                        len(self.global_tm), global_src_file, global_tgt_file)

        self.fallback_translator = fallback_translator

    def _split_to_sent_array(self, text: str) -> List[str]:
        """Split *text* into sentences, further splitting overlong sentences."""
        charlimit = SENT_LEN_LIMIT
        sent_array: List[str] = []
        for sent in self.splitter.split(text):
            while len(sent) > charlimit:
                try:
                    beg = 0
                    while sent[beg] == ' ':
                        beg += 1
                    last_space_idx = sent.rindex(" ", beg, charlimit)
                    sent_array.append(sent[0:last_space_idx])
                    sent = sent[last_space_idx:]
                except ValueError:
                    sent_array.append(sent[0:charlimit])
                    sent = sent[charlimit:]
            sent_array.append(sent)
        return sent_array

    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        """Translate *input_text* using the translation memory.

        The input is split into lines and each line is further split into
        sentences using the sentence splitter.  Each sentence is looked up in
        the TM.  Sentences that are not found are returned unchanged and a
        warning is logged.

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

        for line_idx, line in enumerate(lines):
            is_last_line = line_idx == len(lines) - 1

            if line:
                sents = self._split_to_sent_array(line)
            else:
                sents = [line]

            for sent_idx, sent in enumerate(sents):
                is_last_sent = sent_idx == len(sents) - 1

                if is_last_sent and (not is_last_line or ends_with_newline):
                    suffix = "\n"
                elif not is_last_sent:
                    suffix = " "
                else:
                    suffix = ""

                if sent in self.tm:
                    tgt = self.tm[sent]
                elif (norm_sent := _normalize_ws(sent)) in self.tm_norm:
                    orig_src, tgt = self.tm_norm[norm_sent]
                    logger.warning(
                        "Normalized match in local TM (whitespace): %r -> %r", sent, orig_src
                    )
                elif sent in self.global_tm:
                    logger.warning("Source string not found in local translation memory, falling back to global TM: %r", sent)
                    tgt = self.global_tm[sent]
                elif self.fallback_translator is not None and re.search(r'[^\W\d_]', sent, re.UNICODE):
                    _, tgt_parts = self.fallback_translator.translate(sent)
                    tgt = "".join(tgt_parts).rstrip("\n").rstrip(" ")
                    logger.warning(f"Source string not found in any TM, falling back to the online translator: {sent} -> {tgt}")
                else:
                    if re.search(r'[^\W\d_]', sent, re.UNICODE):
                        logger.warning("Source string not found in translation memory: %r", sent)
                    tgt = sent

                src_sentences.append(sent + suffix)
                tgt_sentences.append(tgt + suffix)

        return src_sentences, tgt_sentences


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="Translate a text file using a translation memory")
    parser.add_argument("input_file", help="Input text file")
    parser.add_argument("src_tm_file", help="Translation memory source file (one sentence per line)")
    parser.add_argument("tgt_tm_file", help="Translation memory target file (one sentence per line)")
    parser.add_argument("src_lang", help="Source language code (e.g. 'de', 'uk')")
    parser.add_argument("--global-src-tm", help="Global TM source file (one sentence per line)", default=None)
    parser.add_argument("--global-tgt-tm", help="Global TM target file (one sentence per line)", default=None)
    args = parser.parse_args()

    translator = TMTranslator(args.src_tm_file, args.tgt_tm_file, args.src_lang,
                              global_src_file=args.global_src_tm, global_tgt_file=args.global_tgt_tm)

    with open(args.input_file, encoding="utf-8") as f_in:
        source = f_in.read()
        src_sentences, tgt_sentences = translator.translate(source)
        print("".join(tgt_sentences), end="")
