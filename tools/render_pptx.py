# -*- coding: utf-8 -*-
"""
Self-contained PPTX -> PNG renderer (python-pptx + Pillow).

Renders only what this demo decks use: solid-fill rectangles, text boxes with
wrapped paragraphs, and tables. No LibreOffice / PDF toolchain required.

Outputs
-------
en-slide{N}.png    English source deck figures
bi-slide{N}.png    bilingual figures (Chinese above, English below)
demo-en-vs-bilingual.pdf   combined, one page per slide
"""
import os
import re

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Emu

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "_out")
OUTDIR = os.path.join(BASE, "figures")
os.makedirs(OUTDIR, exist_ok=True)

DPI = 180.0
EMU_PER_INCH = 914400.0
PX_PER_EMU = DPI / EMU_PER_INCH
PT_TO_PX = DPI / 72.0

FONT_DIR = r"C:\Windows\Fonts"

# cross-platform candidates per role; first existing file wins
FONT_CANDIDATES = {
    "latin": ["segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
              "arial.ttf", "Helvetica.ttc"],
    "latin_bold": ["segoeuib.ttf", "DejaVuSans-Bold.ttf",
                   "LiberationSans-Bold.ttf", "arialbd.ttf"],
    "latin_italic": ["segoeuii.ttf", "DejaVuSans-Oblique.ttf",
                     "LiberationSans-Italic.ttf", "ariali.ttf"],
    "latin_bold_italic": ["segoeuiz.ttf", "DejaVuSans-BoldOblique.ttf",
                          "LiberationSans-BoldItalic.ttf", "arialbi.ttf"],
    "cjk": ["msyh.ttc", "NotoSansCJK-Regular.ttc", "SourceHanSansSC-Regular.otf",
            "wqy-microhei.ttc", "PingFang.ttc"],
    "cjk_bold": ["msyhbd.ttc", "NotoSansCJK-Bold.ttc",
                 "SourceHanSansSC-Bold.otf", "PingFang.ttc"],
}

SEARCH_DIRS = [
    FONT_DIR,
    "/usr/share/fonts", "/usr/share/fonts/truetype", "/usr/local/share/fonts",
    "/System/Library/Fonts", "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]


def _resolve(role):
    for base in SEARCH_DIRS:
        if not os.path.isdir(base):
            continue
        for name in FONT_CANDIDATES[role]:
            direct = os.path.join(base, name)
            if os.path.isfile(direct):
                return direct
        for root, _dirs, files in os.walk(base):
            for name in FONT_CANDIDATES[role]:
                if name in files:
                    return os.path.join(root, name)
    return None


_RESOLVED = {}


def font_path(bold, italic, cjk):
    if cjk:
        role = "cjk_bold" if bold else "cjk"
    elif bold and italic:
        role = "latin_bold_italic"
    elif bold:
        role = "latin_bold"
    elif italic:
        role = "latin_italic"
    else:
        role = "latin"
    if role not in _RESOLVED:
        _RESOLVED[role] = _resolve(role)
    return _RESOLVED[role]


_CACHE = {}


def get_font(size_pt, bold, italic, cjk):
    key = (round(size_pt * 2), bold, italic, cjk)
    if key not in _CACHE:
        path = font_path(bold, italic, cjk)
        px = max(6, int(round(size_pt * PT_TO_PX)))
        _CACHE[key] = (ImageFont.truetype(path, px) if path
                       else ImageFont.load_default())
    return _CACHE[key]


CJK_RE = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def has_cjk(s):
    return bool(CJK_RE.search(s))


def tokenize(text):
    """Split into wrap units: CJK chars individually, latin words whole."""
    units, buf = [], ""
    for ch in text:
        if CJK_RE.match(ch):
            if buf:
                units.append(buf)
                buf = ""
            units.append(ch)
        elif ch == " ":
            buf += ch
            units.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        units.append(buf)
    return units


def wrap(text, font, max_w):
    lines, cur = [], ""
    for u in tokenize(text):
        trial = cur + u
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur.rstrip())
            cur = u.lstrip() if u.strip() else ""
    if cur:
        lines.append(cur.rstrip())
    return lines or [""]


def emu_px(v):
    return int(round(float(Emu(v).inches) * DPI))


def rgb_of(color_fmt):
    try:
        c = color_fmt.rgb
        return (c[0], c[1], c[2])
    except Exception:
        return None


def draw_paragraphs(draw, tf, x, y, w, h, anchor_middle=False):
    """Lay out paragraphs inside a box; returns bottom y."""
    blocks = []
    for p in tf.paragraphs:
        text = "".join(r.text for r in p.runs)
        if not text.strip():
            blocks.append((None, 0, 0))
            continue
        r0 = p.runs[0]
        size = r0.font.size.pt if r0.font.size else 18.0
        bold = bool(r0.font.bold)
        italic = bool(r0.font.italic)
        cjk = has_cjk(text)
        font = get_font(size, bold, italic, cjk)
        color = rgb_of(r0.font.color) or (0x22, 0x28, 0x33)
        lines = wrap(text, font, w)
        after = p.space_after.pt if p.space_after is not None else 0.0
        asc, desc = font.getmetrics()
        line_h = asc + desc
        blocks.append(((lines, font, color, line_h, after), line_h, after))

    total = sum(b[1] + b[2] for b in blocks if b[0])
    cy = y + (h - total) / 2 if anchor_middle else y
    for packed, _, _ in blocks:
        if not packed:
            continue
        lines, font, color, line_h, after = packed
        for ln in lines:
            draw.text((x, cy), ln, font=font, fill=color)
            cy += line_h
        cy += after * PT_TO_PX
    return cy


def render_slide(slide, slide_w, slide_h):
    img = Image.new("RGB", (slide_w, slide_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for shp in slide.shapes:
        left, top = emu_px(shp.left), emu_px(shp.top)
        width, height = emu_px(shp.width), emu_px(shp.height)

        if shp.has_table:
            tbl = shp.table
            col_w = [emu_px(c.width) for c in tbl.columns]
            row_h = [emu_px(r.height) for r in tbl.rows]
            cy = top
            for ri, row in enumerate(tbl.rows):
                cx = left
                for ci in range(len(col_w)):
                    cell = tbl.cell(ri, ci)
                    fill = rgb_of(cell.fill.fore_color) if cell.fill.type == 1 else None
                    if fill:
                        draw.rectangle([cx, cy, cx + col_w[ci], cy + row_h[ri]],
                                       fill=fill)
                    pad = int(0.09 * DPI)
                    tf = cell.text_frame
                    draw_paragraphs(draw, tf, cx + pad, cy + pad * 0.5,
                                    col_w[ci] - 2 * pad, row_h[ri] - pad,
                                    anchor_middle=True)
                    cx += col_w[ci]
                cy += row_h[ri]
            continue

        fill = None
        try:
            if shp.fill.type == 1:
                fill = rgb_of(shp.fill.fore_color)
        except Exception:
            fill = None
        if fill:
            draw.rectangle([left, top, left + width, top + height], fill=fill)
            try:
                if shp.line.fill.type == 1:
                    lc = rgb_of(shp.line.color)
                    if lc:
                        draw.rectangle([left, top, left + width, top + height],
                                       outline=lc, width=2)
            except Exception:
                pass

        if shp.has_text_frame and shp.text_frame.text.strip():
            tf = shp.text_frame
            anchor_mid = False
            try:
                anchor_mid = str(tf.vertical_anchor) == "MIDDLE (3)"
            except Exception:
                pass
            draw_paragraphs(draw, tf, left, top, width, height, anchor_mid)

    return img


def label_image(slide_img, label):
    bar_h = int(0.30 * DPI)
    pad = int(0.06 * DPI)
    w = slide_img.width + pad * 2
    h = bar_h + slide_img.height + pad * 2
    canvas = Image.new("RGB", (w, h), (236, 239, 243))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, w, bar_h], fill=(0x1F, 0x35, 0x64))
    f = get_font(11, True, False, False)
    draw.text((pad + 4, bar_h / 2 - 9), label, font=f, fill=(255, 255, 255))
    canvas.paste(slide_img, (pad, bar_h + pad))
    draw.rectangle([pad, bar_h + pad, pad + slide_img.width - 1,
                    bar_h + pad + slide_img.height - 1],
                   outline=(184, 192, 204), width=2)
    return canvas


def render_deck(pptx_name, prefix, label_fmt):
    prs = Presentation(os.path.join(SRC, pptx_name))
    sw = emu_px(prs.slide_width)
    sh = emu_px(prs.slide_height)
    imgs = []
    for i, slide in enumerate(prs.slides, start=1):
        s = render_slide(slide, sw, sh)
        fig = label_image(s, label_fmt.format(n=i))
        p = os.path.join(OUTDIR, f"{prefix}-slide{i}.png")
        fig.save(p)
        imgs.append(fig)
        print(f"[i] wrote {p}  ({fig.width}x{fig.height})")
    return imgs


def build_comparison(en_imgs, bi_imgs):
    pages = []
    gap, margin, bar_h = int(0.16 * DPI), int(0.18 * DPI), int(0.28 * DPI)
    label_h = int(0.20 * DPI)
    for i, (a, b) in enumerate(zip(en_imgs, bi_imgs), start=1):
        # page is scaled down for a PDF-friendly width
        page_w = 1600
        scale = page_w / (a.width * 2 + gap + margin * 2)
        aw = int(a.width * scale)
        ah = int(a.height * scale)
        page_h = bar_h + label_h + ah + margin
        page = Image.new("RGB", (page_w, page_h), (255, 255, 255))
        d = ImageDraw.Draw(page)
        d.rectangle([0, 0, page_w, bar_h], fill=(0x1F, 0x35, 0x64))
        f = get_font(10.5, True, False, False)
        d.text((margin, bar_h / 2 - 8),
               f"Slide {i}   \u00b7   English source (left)   vs   "
               f"bilingual output (right)",
               font=f, fill=(255, 255, 255))
        y0 = bar_h + label_h
        for k, (im, cap) in enumerate(((a, "English source"),
                                       (b, "Bilingual: ZH above / EN below"))):
            x = margin + k * (aw + gap)
            small = im.resize((aw, ah), Image.LANCZOS)
            page.paste(small, (x, y0))
            d.rectangle([x, y0, x + aw - 1, y0 + ah - 1],
                        outline=(184, 192, 204), width=2)
            fl = get_font(9, True, False, False)
            d.text((x, y0 - label_h + 4), cap, font=fl, fill=(60, 68, 80))
        pages.append(page)

    out = os.path.join(OUTDIR, "demo-en-vs-bilingual.pdf")
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150.0)
    print(f"[i] wrote {out} ({len(pages)} pages)")


if __name__ == "__main__":
    en = render_deck("demo-original-en.pptx", "en",
                     "Slide {n}   \u00b7   English source deck")
    bi = render_deck("demo-bilingual-zh-en.pptx", "bi",
                     "Slide {n}   \u00b7   Bilingual output "
                     "(Chinese above, English below)")
    build_comparison(en, bi)
    print("[OK] done")
