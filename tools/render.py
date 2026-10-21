# -*- coding: utf-8 -*-
"""
Render the demo deck pair to PNG pages and build side-by-side comparison
figures: left = original (EN), right = translated (ZH).
"""
import os
import pymupdf

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "figures")
os.makedirs(OUTDIR, exist_ok=True)

EN_PDF = os.path.join(BASE, "_out", "demo-original-en.pdf")
ZH_PDF = os.path.join(BASE, "_out", "demo-translated-zh.pdf")

LABEL_EN = "Original (English)"
LABEL_ZH = "Translated (Chinese) - layout preserved"

PAGE_W, PAGE_H = 826, 1169        # A4 portrait, points
MARGIN = 30
BAR_H = 38


def make_comparison():
    en = pymupdf.open(EN_PDF)
    zh = pymupdf.open(ZH_PDF)
    n = min(len(en), len(zh))
    print(f"[i] pages: en={len(en)} zh={len(zh)} -> composing {n}")

    comp_doc = pymupdf.open()
    for i in range(n):
        page = comp_doc.new_page(width=PAGE_W, height=PAGE_H)
        # header bar
        page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, BAR_H), color=None, fill=(0.12, 0.21, 0.39))
        page.insert_text((MARGIN, BAR_H / 2 + 4),
                         f"Slide {i + 1}  \u00b7  layout-fidelity comparison",
                         fontsize=12, fontname="helv", color=(1, 1, 1))

        avail_w = PAGE_W - 2 * MARGIN
        gap = 46
        avail_h = (PAGE_H - BAR_H - 2 * MARGIN - 30 - gap) / 2

        en_page = en[i]
        zh_page = zh[i]
        ar = en_page.rect.width / en_page.rect.height

        w = avail_w
        h = w / ar
        if h > avail_h:
            h = avail_h
            w = h * ar

        y_top = BAR_H + MARGIN + 20
        y_bot = y_top + h + gap

        for y, src, label in ((y_top, en_page, LABEL_EN),
                              (y_bot, zh_page, LABEL_ZH)):
            rect = pymupdf.Rect(MARGIN, y, MARGIN + w, y + h)
            page.show_pdf_page(rect, src.parent, src.number, rotate=0)
            page.draw_rect(rect, color=(0.78, 0.80, 0.84), width=0.9)
            page.insert_text((MARGIN, y - 8), label, fontsize=10.5,
                             fontname="helv", color=(0.20, 0.25, 0.32))

        # footer
        page.insert_textbox(
            pymupdf.Rect(MARGIN, PAGE_H - MARGIN - 22, PAGE_W - MARGIN, PAGE_H - MARGIN),
            "Synthetic demo data \u2014 no client content.  Chinese text is longer, "
            "yet boxes, colours and text hierarchy stay identical.",
            fontsize=8, fontname="helv", color=(0.45, 0.48, 0.52))

        # export page at 200 dpi
        pix = page.get_pixmap(dpi=200)
        outp = os.path.join(OUTDIR, f"slide-{i + 1}-compare.png")
        pix.save(outp)
        print(f"[i] wrote {outp}  ({pix.width}x{pix.height})")

    comp_pdf = os.path.join(OUTDIR, "translation-comparison.pdf")
    comp_doc.save(comp_pdf)
    print(f"[i] wrote {comp_pdf}")
    comp_doc.close()
    en.close()
    zh.close()


def make_single_pages():
    """Individual full-size renders (useful for README hero image)."""
    for tag, path in (("original-en", EN_PDF), ("translated-zh", ZH_PDF)):
        doc = pymupdf.open(path)
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(dpi=170)
            outp = os.path.join(OUTDIR, f"{tag}-slide{i + 1}.png")
            pix.save(outp)
            print(f"[i] wrote {outp} ({pix.width}x{pix.height})")
        doc.close()


if __name__ == "__main__":
    make_comparison()
    make_single_pages()
    print("[OK] done")
