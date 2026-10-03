"""Prepare ASCII 3270 faces, including synthetic bold and italic for PDFs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'BUILD/pdf-deps'))
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen

ASSETS = ROOT / 'tools/pdf-fonts/ibm3270'


def main():
    for bold, italic, style in ((False, False, 'Regular'), (True, False, 'Bold'),
                                 (False, True, 'Italic'), (True, True, 'BoldItalic')):
        font = TTFont(ASSETS / '3270-Regular.ttf')
        options = subset.Options()
        options.name_IDs = ['*']
        selected = subset.Subsetter(options=options)
        selected.populate(unicodes=range(32, 127))
        selected.subset(font)
        glyphs = font.getGlyphSet()
        outlines = {}
        weight = round(font['head'].unitsPerEm * .026)
        for name in font.getGlyphOrder():
            pen = TTGlyphPen(glyphs)
            shear = .20 if italic else 0
            glyphs[name].draw(TransformPen(pen, (1, 0, shear, 1, 0, 0)))
            if bold:
                glyphs[name].draw(TransformPen(pen, (1, 0, shear, 1, weight, 0)))
            outlines[name] = pen.glyph()
        for name, glyph in outlines.items():
            font['glyf'][name] = glyph
        font['head'].macStyle = int(bold) | int(italic) << 1
        font['OS/2'].usWeightClass = 700 if bold else 400
        font['OS/2'].fsSelection = (int(bold) << 5) | int(italic)
        if not bold and not italic:
            font['OS/2'].fsSelection |= 1 << 6
        font['post'].italicAngle = -11.3 if italic else 0
        family = 'STR8N 3270'
        for record in font['name'].names:
            values = {1: family, 2: style, 3: f'{family} {style}',
                      4: f'{family} {style}', 6: f'STR8N3270-{style}',
                      16: family, 17: style}
            if record.nameID in values:
                record.string = values[record.nameID].encode(record.getEncoding())
        target = ASSETS / f'STR8N3270-{style}.ttf'
        font.save(target)
        print(target)


if __name__ == '__main__':
    main()
