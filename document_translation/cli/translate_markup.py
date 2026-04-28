import logging
import argparse

from document_translation.lindat_services.align import LindatAligner
from document_translation.markuptranslator import MarkupTranslator
from document_translation.regextokenizer import RegexTokenizer
from document_translation.lindat_services.translate import LindatTranslator
from document_translation.lindat_services.edukate_translate import EdukateTranslator
from document_translation.tm_translator import TMTranslator


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for _logger in loggers:
    _logger.setLevel(logger.level)

def main():
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('input_file', help='Input text file with markup')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('tgt_lang', help='Target language')
    parser.add_argument('model', nargs='?', default=None,
                        help='Translation model (Lindat MT); if --tm is also provided, used as fallback for TM misses')
    parser.add_argument('output_file', help='Output text file')
    parser.add_argument('--tm', nargs=2, metavar=('SRC_TM', 'TGT_TM'),
                        help='Use translation memory; '
                             'provide paths to the source and target TM files')
    parser.add_argument('--global-tm', nargs=2, metavar=('GLOBAL_SRC_TM', 'GLOBAL_TGT_TM'),
                        help='Global translation memory to fall back to when --tm is used; '
                             'provide paths to the source and target global TM files')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    if args.model is None and args.tm is None:
        parser.error('one of model (positional) or --tm SRC_TM TGT_TM is required')

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for _logger in loggers:
            _logger.setLevel(logger.level)

    online_translator = None
    if args.model and "edukate" in args.model:
        # service name and model name are delimited by a colon
        service_name, model_name = args.model.split(":", 1)
        online_translator = EdukateTranslator(args.src_lang, args.tgt_lang, service_name, model_name)
    elif args.model:
        online_translator = LindatTranslator(args.src_lang, args.tgt_lang, args.model)
    if args.tm:
        global_src, global_tgt = (args.global_tm if args.global_tm else (None, None))
        translator = TMTranslator(args.tm[0], args.tm[1], args.src_lang,
                                  global_src_file=global_src, global_tgt_file=global_tgt,
                                  fallback_translator=online_translator)
    else:
        translator = online_translator
    aligner = LindatAligner(args.src_lang, args.tgt_lang)
    tokenizer = RegexTokenizer()
    mt = MarkupTranslator(translator, aligner, tokenizer)

    with open(args.input_file) as f_in, open(args.output_file, "w") as f_out:
        input_text = f_in.read()
        output = mt.translate(input_text)
        f_out.write(output)

if __name__ == "__main__":
    main()