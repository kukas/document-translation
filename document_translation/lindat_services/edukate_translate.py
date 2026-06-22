import requests
from typing import List, Tuple

from document_translation.markuptranslator import Translator


class EdukateTranslator(Translator):
    """Translator backed by the Edukate online translation service.

    Equivalent curl call::

        curl -F input_text="<text>" '<url>'

    The service accepts plain text (one paragraph per line) and returns
    translated plain text (one line per input line).
    """

    def __init__(self, src_lang: str, tgt_lang: str, service_name: str, model_name: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.url = f"https://quest.ms.mff.cuni.cz/{service_name}/api/v2/models/{model_name}?src={src_lang}&tgt={tgt_lang}"

    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        if input_text == "":
            return [], []

        response = requests.post(self.url, data={"input_text": input_text})
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}\n{response.text}")

        response.encoding = "utf-8"
        src_lines = input_text.splitlines(keepends=True)
        tgt_lines = response.text.splitlines(keepends=True)
        assert len(src_lines) == len(tgt_lines), f"{len(src_lines)} != {len(tgt_lines)}"

        return src_lines, tgt_lines
