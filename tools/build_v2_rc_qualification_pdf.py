"""Render the editable W65C816SXB/EDU RC1 checklist as a print-ready PDF."""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs/STR8N_V2_RC1_816_QUALIFICATION_CHECKLIST.md"
OUTPUT = ROOT / "output/pdf/STR8N_V2_RC1_816_QUALIFICATION_CHECKLIST.pdf"
WIDTH, HEIGHT = letter
LEFT = 45
RIGHT = WIDTH - 45
TOP = HEIGHT - 58
BOTTOM = 52
FONT_DIR = Path.home() / "AppData/Local/Microsoft/Windows/Fonts"


def register_3270_fonts() -> None:
    for name, filename in (
        ("IBM3270", "3270-Medium 500.ttf"),
        ("IBM3270SemiNarrow", "3270 Semi-Narrow 500.ttf"),
    ):
        path = FONT_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required resident 3270 font: {path}")
        pdfmetrics.registerFont(TTFont(name, str(path)))


def plain(line: str) -> str:
    line = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", line)
    return line.replace("**", "").replace("`", "")


def wrapped(line: str, font: str, size: float) -> list[str]:
    words = plain(line).split()
    if not words:
        return [""]
    result: list[str] = []
    current = ""
    for word in words:
        proposal = f"{current} {word}" if current else word
        if pdfmetrics.stringWidth(proposal, font, size) <= RIGHT - LEFT:
            current = proposal
        else:
            if current:
                result.append(current)
            if pdfmetrics.stringWidth(word, font, size) > RIGHT - LEFT:
                raise ValueError(f"unbreakable line too wide: {word}")
            current = word
    if current:
        result.append(current)
    return result


def main() -> None:
    register_3270_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=letter, pageCompression=1)
    pdf.setTitle("STR8-N 2.0a21 RC1 W65C816SXB/EDU qualification record")
    page = 1
    y = TOP
    field_count = 0

    def header() -> None:
        pdf.setFont("IBM3270", 10)
        pdf.drawString(LEFT, HEIGHT - 35, "STR8-N 2.0a21 RC1  |  W65C816SXB / EDU")
        pdf.setLineWidth(0.5)
        pdf.line(LEFT, HEIGHT - 40, RIGHT, HEIGHT - 40)

    def footer() -> None:
        pdf.line(LEFT, 42, RIGHT, 42)
        pdf.setFont("IBM3270", 8)
        pdf.drawString(LEFT, 29, "Board qualification record  |  Complete one copy per SXB")
        pdf.drawRightString(RIGHT, 29, f"Page {page}")

    def next_page() -> None:
        nonlocal page, y
        footer()
        pdf.showPage()
        page += 1
        header()
        y = TOP

    header()
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        if raw.strip() == "<!-- PAGE BREAK -->":
            next_page()
            continue
        if not raw.strip():
            y -= 5
            continue
        if raw.startswith("# "):
            font, size, leading, value = "IBM3270", 14, 18, plain(raw[2:])
        elif raw.startswith("## "):
            font, size, leading, value = "IBM3270", 11, 15, plain(raw[3:])
        else:
            font, size, leading, value = "IBM3270SemiNarrow", 9, 11.5, plain(raw)
        for part in wrapped(value, font, size):
            if y - leading < BOTTOM:
                next_page()
            pdf.setFont(font, size)
            pdf.drawString(LEFT, y, part)
            if not raw.startswith("#"):
                for match in re.finditer(r"\[ \]|_{4,}", part):
                    field_count += 1
                    x = LEFT + pdfmetrics.stringWidth(part[:match.start()], font, size)
                    width = pdfmetrics.stringWidth(match.group(), font, size)
                    if match.group() == "[ ]":
                        pdf.acroForm.checkbox(
                            name=f"check_{field_count}", tooltip=part[:90],
                            x=x + 1, y=y - 1, size=8,
                            borderColor=colors.black, fillColor=colors.white,
                            textColor=colors.black, borderWidth=0.7,
                            fieldFlags="", annotationFlags="print",
                        )
                    else:
                        pdf.acroForm.textfield(
                            name=f"entry_{field_count}", tooltip=part[:90],
                            x=x, y=y - 2, width=width, height=11,
                            fontName="Helvetica", fontSize=9,
                            textColor=colors.black, fillColor=colors.white,
                            borderColor=colors.black, borderWidth=0.4,
                            borderStyle="underlined", maxlen=180,
                            fieldFlags="", annotationFlags="print",
                        )
            y -= leading
    footer()
    pdf.save()
    print(f"{OUTPUT.relative_to(ROOT)} ({page} pages; {field_count} fillable fields)")


if __name__ == "__main__":
    main()
