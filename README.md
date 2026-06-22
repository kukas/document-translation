# Formatted document translation

Automatically translate documents with **formatted** text such as Word, Powerpoint, RTF, HTML but also XML or even PDF!

In this repository, we implement an end-to-end system for machine translation of documents. We build on top of [Okapi Framework](https://okapiframework.org/) and provide a simple script that extracts translatable, formatted text from documents and translates them, **preserving the formatting**. We preserve the in-line formatting by reinserting the markup into the translated document.

## Features

- [Python module](document_translation/) for automatic tag extraction from text and reinsertion of tags into translated text.
- [Helpers for translation and word alignment](document_translation/lindat_services/) using [LINDAT public service APIs](https://lindat.cz/services/)
- [Command-line interface for translating translation units with inline elements](translate_markup.py) in the [Moses InlineText](https://okapiframework.org/wiki/index.php/Moses_Text_Filter) format corresponding to the [XLIFF v1.2 translation unit format](http://docs.oasis-open.org/xliff/v1.2/os/xliff-core.html#Struct_InLine).
- [Command-line interface for translating PDF documents](translate_pdf.py)
- An [example script](examples/word_document) for translating documents with wide range of formats utilizing the [Okapi Framework](https://okapiframework.org/)

## Installation

The Python module can be installed using pip from this repository:

```bash
pip install git+https://github.com/ufal/document-translation.git
```

The module allows you to automatically translate Moses InlineText files and PDF documents.

To translate a wider variety of formats, install the [Okapi Framework](https://okapiframework.org/).

## Usage

See the [examples](examples/) directory for usage examples.

## Translating text with markup

How is translating formatted text different from non-formatted text? Consider the following example:

- Original: `He is a <b>friend</b> of mine.`
- Input to the translator: `He is a friend of mine.`
- Translation: `Er ist mein Freund.`
- Reinserted markup: `Er ist mein <b>Freund</b>.`

Machine translation systems work best when the input is stripped of any formatting tags such as the bold tag `<b>`. This is because they have been mostly trained on data without these markup tags. When we get rid of the markup, the translation is more accurate but we introduce a new problem --- we need to reinsert the formatting tags back into the translation to preserve the original formatting.

We do this by running a word alignment model that gives us information about which word in the original sentence corresponds to which word in the translated sentence. We then reinsert the markup back into the translation using this information.
