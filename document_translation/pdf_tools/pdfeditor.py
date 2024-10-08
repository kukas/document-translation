import fitz
from typing import List
import os
font_path = os.path.join(os.path.dirname(__file__), "..", "fonts")

class PdfEditor:
    # TODO: use importlib https://setuptools.pypa.io/en/latest/userguide/datafiles.html#accessing-data-files-at-runtime
    flag_to_static_font = {
        # https://pymupdf.readthedocs.io/en/latest/textpage.html#span-dictionary
        # “flags” is an integer, which represents font properties except for the first bit 0. They are to be interpreted like this:
        # bit 0: superscripted (20) – not a font property, detected by MuPDF code.
        # bit 1: italic (21)
        # bit 2: serifed (22)
        # bit 3: monospaced (23)
        # bit 4: bold (24)
        0b01000: ('NotoSansMono-Regular', font_path+'/Noto_Sans_Mono/static/NotoSansMono-Regular.ttf'),
        0b01010: ('NotoSansMono-Regular', font_path+'/Noto_Sans_Mono/static/NotoSansMono-Regular.ttf'),
        0b11000: ('NotoSansMono-Bold', font_path+'/Noto_Sans_Mono/static/NotoSansMono-Bold.ttf'),
        0b11010: ('NotoSansMono-Bold', font_path+'/Noto_Sans_Mono/static/NotoSansMono-Bold.ttf'),
        0b00100: ('NotoSerif-Regular', font_path+'/Noto_Serif/static/NotoSerif-Regular.ttf'),
        0b00110: ('NotoSerif-Italic', font_path+'/Noto_Serif/static/NotoSerif-Italic.ttf'),
        0b10100: ('NotoSerif-Bold', font_path+'/Noto_Serif/static/NotoSerif-Bold.ttf'),
        0b10110: ('NotoSerif-BoldItalic', font_path+'/Noto_Serif/static/NotoSerif-BoldItalic.ttf'),
        0b00000: ('NotoSans-Regular', font_path+'/Noto_Sans/static/NotoSans-Regular.ttf'),
        0b00010: ('NotoSans-Italic', font_path+'/Noto_Sans/static/NotoSans-Italic.ttf'),
        0b10000: ('NotoSans-Bold', font_path+'/Noto_Sans/static/NotoSans-Bold.ttf'),
        0b10010: ('NotoSans-BoldItalic', font_path+'/Noto_Sans/static/NotoSans-BoldItalic.ttf'),
    }

    def __init__(self, input_file):
        self.doc = fitz.open(input_file)
        self.new_doc = False
        flags = fitz.TEXT_PRESERVE_WHITESPACE
        self.texts = [page.get_text("dict", flags=flags) for page in self.doc]

    def get_font(self, span):
        # we replace the pdf fonts because the embedded fonts don't have necessarily all the characters
        # an alternative would be to use the standard Base-14 fonts, but MuPDF somehow also doesn't have all the characters
        # we therefore use the Noto fonts that contain all the characters we need

        font = span["font"]

        # These fonts from Base-14 are not replaced by our static fonts
        base14_allowed = ["Symbol", "ZapfDingbats"]
        if font in base14_allowed or ("+" in font and font.split("+")[1] in base14_allowed):
            return (font, None)

        flags = span["flags"]
        # remove the first bit
        #   bit 0: superscripted (20) – not a font property, detected by MuPDF code.
        flags = flags & 0b11110
        return self.flag_to_static_font.get(flags, self.flag_to_static_font[0b00000])


    def extract_text(self):
        print("extracting texts")
        texts = []
        for wlist in self.texts:
            for block in wlist["blocks"]:
                if "lines" not in block: continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        texts.append(span["text"])
            texts.append("<page-break />")
        return texts

    def merge_text(self, translated_lines: List[str], output_file):
        print("inserting texts")
        n_didnt_fit = 0
        line_num = 0
        DRAW_BOUNDING_BOX = 0b000
        page_num = 0
        for page, wlist in zip(self.doc, self.texts):
            # if not wlist["blocks"]:
            #     return
            for block in wlist["blocks"]:
                if "lines" not in block: continue
                if DRAW_BOUNDING_BOX & 0b100:
                    page.draw_rect(block["bbox"], color=(1, 0, 0), width=1, stroke_opacity=0.5)
                for line in block["lines"]:
                    if DRAW_BOUNDING_BOX & 0b10:
                        page.draw_rect(line["bbox"], color=(0, 1, 0), width=1, stroke_opacity=0.5)
                    for span in line["spans"]:
                        if DRAW_BOUNDING_BOX & 0b1:
                            page.draw_rect(span["bbox"], color=(0, 0, 1), width=1, stroke_opacity=0.5)
                        page.add_redact_annot(span["bbox"])
            page.apply_redactions(graphics=0)

            # block by block replacement
            for block in wlist["blocks"]:
                if "lines" not in block: continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        # color
                        c = span['color']
                        c = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
                        c = c[0]/255, c[1]/255, c[2]/255

                        # font
                        fontname, fontfile = self.get_font(span)
                        xref = page.insert_font(fontname=fontname, fontfile=fontfile)

                        # size
                        text = translated_lines[line_num]
                        line_num += 1
                        size = span["size"]*0.8 # start with smaller font size so that the translation fits
                        max_length = span["bbox"][2] - span["bbox"][0]
                        font_obj = fitz.Font(fontfile=fontfile)
                        while True:
                            text_length = font_obj.text_length(text, fontsize=size)
                            if text_length <= max_length or size < 3:
                                break
                            size -= 0.2
                            n_didnt_fit += 1

                        page.insert_text(span["origin"], text, fontsize=size, set_simple=False, color=c, fontname=fontname, fontfile=None)
            
            assert translated_lines[line_num] == "<page-break />"
            line_num += 1
            page_num += 1

        print(f"{n_didnt_fit} texts didn't fit")

        self.doc.save(output_file, garbage=4, clean=True, deflate=True, deflate_images=True, deflate_fonts=True)
