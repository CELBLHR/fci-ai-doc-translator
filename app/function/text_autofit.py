# -*- coding: utf-8 -*-
"""
不依赖 LibreOffice 的文本框自适应（shrink-on-overflow）实现。

思路
----
PowerPoint 的"溢出时缩排"真值是 OOXML 里的一个数字：

    <a:bodyPr><a:normAutofit fontScale="62500" lnSpcReduction="0"/></a:bodyPr>

fontScale 单位是 1/1000 百分比（62500 = 62.5%）。python-pptx 设
`text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` 只会写一个**空的**
`<a:normAutofit/>`，没有 fontScale，所以必须靠某个渲染器补上——这就是原来
依赖 LibreOffice 转换的原因。

本模块把这层渲染器依赖去掉：
  1. 用真实字体文件度量（advance width / ascent / descent）做断行
  2. 二分搜索出刚好放得下的缩放比
  3. 直接写回 fontScale

全程只修改 `<a:bodyPr>` 的子节点，不触碰主题、母版、背景、媒体等任何其他 part。
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

from lxml import etree
from pptx.oxml.ns import qn

EMU_PER_PT = 12700.0
MIN_SCALE = 0.25          # PowerPoint 实际可用的下限
SAFETY = 0.99             # 偏保守：算完后多缩 1%，宁可小一号也不溢出
REF_PX = 200              # 度量参考字号（像素），advance width 与字号线性相关
# PowerPoint 单倍行距固定为 1.2 × 字号（实测 21.6 = 18pt × 1.2），
# 与字体自身的 hhea 行高无关，必须用这个系数才对得上渲染结果。
LINE_HEIGHT_FACTOR = 1.2
# 断行时给宽度一点余量：字体 advance 与 PowerPoint 排版有 ~1% 差异，
# 不留余量会提前断行、多算一行。
WRAP_TOLERANCE = 1.02
SCALE_STEP = 0.05         # 与 PowerPoint 一致：按 5% 步进量化
# 只用到 97% 的可用高度，避免断行差一行时贴边溢出
TARGET_FILL = 0.97

CJK_RE = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]")


# --------------------------------------------------------------------- 字体
FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/System/Library/Fonts",
]

# 名称别名 -> (常规字体文件名, 粗体文件名)
FONT_ALIASES: Dict[str, Tuple[List[str], List[str]]] = {
    "segoe ui": (["segoeui.ttf"], ["segoeuib.ttf"]),
    "calibri": (["calibri.ttf"], ["calibrib.ttf"]),
    "arial": (["arial.ttf"], ["arialbd.ttf"]),
    "times new roman": (["times.ttf"], ["timesbd.ttf"]),
    "helvetica": (["arial.ttf"], ["arialbd.ttf"]),
    "微软雅黑": (["msyh.ttc"], ["msyhbd.ttc"]),
    "microsoft yahei": (["msyh.ttc"], ["msyhbd.ttc"]),
    "宋体": (["simsun.ttc"], ["simsun.ttc"]),
    "simsun": (["simsun.ttc"], ["simsun.ttc"]),
    "黑体": (["simhei.ttf"], ["simhei.ttf"]),
    "simhei": (["simhei.ttf"], ["simhei.ttf"]),
    "思源黑体": (["SourceHanSansSC-Regular.otf"], ["SourceHanSansSC-Bold.otf"]),
    "noto sans cjk sc": (["NotoSansCJK-Regular.ttc"], ["NotoSansCJK-Bold.ttc"]),
}

# 找不到字体时的兜底：拉丁 / CJK 的近似字符宽度（em 比例）
FALLBACK_EM = {"cjk": 1.0, "latin": 0.52}


def _find_file(names: List[str]) -> Optional[str]:
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


class FontMetrics:
    """缓存字体度量：宽度按 em 比例存，避免每个字号重复打开字体。"""

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, bool], Dict[str, object]] = {}

    def _load(self, font_name: Optional[str], bold: bool):
        key = ((font_name or "").strip().lower(), bold)
        if key in self._cache:
            return self._cache[key]

        spec = FONT_ALIASES.get(key[0]) if key[0] else None
        path = None
        if spec:
            path = _find_file(spec[1] if bold else spec[0])
        if not path:
            # 退化：CJK 用雅黑，拉丁用 Segoe UI，再不行用 Arial
            path = (_find_file(["msyhbd.ttc" if bold else "msyh.ttc"])
                    or _find_file(spec[0] if spec else [])
                    or _find_file(["segoeuib.ttf" if bold else "segoeui.ttf"])
                    or _find_file(["arialbd.ttf" if bold else "arial.ttf"]))

        info: Dict[str, object] = {"path": path, "font": None,
                                   "ascent_em": 0.8, "descent_em": 0.2}
        if path:
            try:
                from PIL import ImageFont
                f = ImageFont.truetype(path, REF_PX)
                asc, desc = f.getmetrics()
                info["font"] = f
                info["ascent_em"] = asc / REF_PX
                info["descent_em"] = desc / REF_PX
            except Exception:
                pass
        self._cache[key] = info
        return info

    def width_pt(self, text: str, font_name: Optional[str], size_pt: float,
                 bold: bool) -> float:
        if not text:
            return 0.0
        info = self._load(font_name, bold)
        f = info["font"]
        if f is not None:
            try:
                return f.getlength(text) / REF_PX * size_pt
            except Exception:
                pass
        # 兜底：CJK 全宽、拉丁半宽
        em = sum(FALLBACK_EM["cjk"] if CJK_RE.match(ch) else FALLBACK_EM["latin"]
                 for ch in text)
        return em * size_pt

    def cjk_line_height_pt(self, font_name: Optional[str], size_pt: float,
                           bold: bool) -> float:
        """中文：行高取决于字体本身（微软雅黑约 1.32em，高于 1.2）。"""
        info = self._load(font_name, bold)
        natural = (info["ascent_em"] + info["descent_em"]) * size_pt
        return max(LINE_HEIGHT_FACTOR * size_pt, natural)

    def line_height_pt(self, font_name: Optional[str], size_pt: float,
                       bold: bool) -> float:
        """PowerPoint 单倍行距 = 1.2 × 字号（已用 COM 基准实测校验）。"""
        return LINE_HEIGHT_FACTOR * size_pt


# ------------------------------------------------------------------ 断行
def _line_h(metrics, fname, size, bold, text: str) -> float:
    """按内容选择行高：含中文用字体真实行高，纯西文用 1.2×字号。"""
    if CJK_RE.search(text or ""):
        fn = getattr(metrics, "cjk_line_height_pt", None)
        if fn is not None:
            return fn(fname, size, bold)
    return metrics.line_height_pt(fname, size, bold)

def tokenize(text: str) -> List[str]:
    """把一行拆成不可再分的排版单元：CJK 单字，拉丁词（含尾随空格）。"""
    units: List[str] = []
    buf = ""
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


def wrap_segments(segments, max_w_pt: float, metrics: FontMetrics) -> List[float]:
    """
    segments: [(text, font_name, size_pt, bold)]
    返回每一行的高度（pt）列表。
    """
    lines: List[float] = []      # 每行的行高
    cur_w = 0.0
    cur_h = 0.0
    started = False

    last_size = 0.0
    for seg in segments:
        if seg is None:                     # a:br 强制换行
            lines.append(cur_h if started else last_size * LINE_HEIGHT_FACTOR)
            cur_w = 0.0
            cur_h = 0.0
            started = False
            continue
        text, fname, size, bold = seg
        last_size = size
        for unit in tokenize(text):
            w = metrics.width_pt(unit, fname, size, bold)
            h = _line_h(metrics, fname, size, bold, unit)
            if started and cur_w + w > max_w_pt:
                lines.append(cur_h)
                cur_w = 0.0
                cur_h = 0.0
                started = False
                unit = unit.lstrip()
                if not unit:
                    continue
                w = metrics.width_pt(unit, fname, size, bold)
            cur_w += w
            cur_h = max(cur_h, h)
            started = True

    lines.append(cur_h if started else (cur_h or 0.0))
    return lines


# ------------------------------------------------------------------ 排版估算
def _emu_to_pt(v) -> float:
    return float(int(v)) / EMU_PER_PT


def _group_scale(shape) -> Tuple[float, float]:
    """累乘所有上层组合（grpSp）的 chExt→ext 缩放，得到实际渲染尺寸比例。

    shape 可能是 _Cell（没有 _element），此时退化为 1.0。
    """
    sx = sy = 1.0
    el = getattr(shape, "_element", None)
    if el is None:
        return sx, sy
    parent = el.getparent()
    while parent is not None:
        if parent.tag == qn("p:grpSp"):
            xfrm = parent.find(qn("p:grpSpPr"))
            xfrm = xfrm.find(qn("a:xfrm")) if xfrm is not None else None
            if xfrm is not None:
                ext = xfrm.find(qn("a:ext"))
                ch = xfrm.find(qn("a:chExt"))
                if ext is not None and ch is not None:
                    try:
                        if int(ch.get("cx")) > 0:
                            sx *= int(ext.get("cx")) / int(ch.get("cx"))
                        if int(ch.get("cy")) > 0:
                            sy *= int(ext.get("cy")) / int(ch.get("cy"))
                    except (TypeError, ValueError):
                        pass
        parent = parent.getparent()
    return sx, sy


def _paragraph_segments(para, scale: float, default_size: float):
    """把段落拆成排版单元，正确处理 <a:br/> 软换行与逐 run 字号。

    换行是 run 的**兄弟节点**（`<a:p><a:r/><a:br/><a:r/></a:p>`），
    不在 run.text 里，所以必须遍历段落 XML 子元素，不能只看 para.runs。
    """
    segs = []
    for child in para._p:
        tag = etree.QName(child).localname
        if tag == "br":
            segs.append(None)                 # 强制换行
            continue
        if tag not in ("r", "fld"):
            continue
        t_el = child.find(qn("a:t"))
        text = (t_el.text or "") if t_el is not None else ""
        if not text:
            continue
        rPr = child.find(qn("a:rPr"))
        size = None
        bold = False
        fname = None
        if rPr is not None:
            sz = rPr.get("sz")
            if sz:
                try:
                    size = int(sz) / 100.0
                except ValueError:
                    size = None
            bold = rPr.get("b") in ("1", "true")
            latin = rPr.find(qn("a:latin"))
            if latin is not None:
                fname = latin.get("typeface")
        if size is None:
            size = default_size
        segs.append((text, fname, size * scale, bold))
    return segs


def measure_frame(tf, shape, metrics: FontMetrics, scale: float = 1.0,
                  default_size: float = 18.0):
    """返回 (所需高度pt, 可用宽度pt, 可用高度pt, 实际行数)。"""
    sx, sy = _group_scale(shape)
    avail_w = (_emu_to_pt(shape.width) * sx
               - _emu_to_pt(tf.margin_left) - _emu_to_pt(tf.margin_right))
    avail_h = (_emu_to_pt(shape.height) * sy
               - _emu_to_pt(tf.margin_top) - _emu_to_pt(tf.margin_bottom))
    avail_w = max(avail_w, 1.0)

    wrap = tf.word_wrap is not False       # None 视作按主题默认（通常开启）
    total_h = 0.0
    total_lines = 0

    for para in tf.paragraphs:
        size_hint = default_size
        if para.font.size is not None:
            size_hint = para.font.size.pt
        segments = _paragraph_segments(para, scale, size_hint)

        if not segments:
            # 空段落仍占一行高度
            total_h += metrics.line_height_pt(None, 14.0 * scale, False)
            total_lines += 1
            continue

        if wrap:
            line_hs = wrap_segments(segments, avail_w * WRAP_TOLERANCE, metrics)
        else:
            heights = [metrics.line_height_pt(seg[1], seg[2], seg[3])
                       for seg in segments if seg is not None]
            line_hs = [max(heights)] if heights else [
                metrics.line_height_pt(None, default_size * scale, False)]
        # 行距：倍数（spcPct）按倍数缩放；固定值（spcPts）直接取该高度
        ls = para.line_spacing
        if isinstance(ls, float):
            block = sum(line_hs) * ls
        elif ls is not None and hasattr(ls, "pt"):
            block = len(line_hs) * float(ls.pt) * scale
        else:
            block = sum(line_hs)
        if para.space_before is not None:
            block += _emu_to_pt(para.space_before) * scale
        if para.space_after is not None:
            block += _emu_to_pt(para.space_after) * scale
        total_h += block
        total_lines += len(line_hs)

    return total_h, avail_w, avail_h, total_lines



def compute_scale(tf, shape, metrics: FontMetrics,
                  max_scale: float = 1.0) -> Tuple[float, Dict[str, float]]:
    """二分搜索刚好放得下的缩放比。"""
    need, aw, ah, lines = measure_frame(tf, shape, metrics, 1.0)
    info = {"need_h": need, "avail_h": ah, "avail_w": aw, "lines": lines}
    target_h = ah * TARGET_FILL
    if need <= target_h:
        return 1.0, info
    lo, hi = MIN_SCALE, max_scale
    if measure_frame(tf, shape, metrics, lo)[0] > target_h:
        return MIN_SCALE, info          # 缩到下限仍放不下
    for _ in range(14):
        mid = (lo + hi) / 2
        if measure_frame(tf, shape, metrics, mid)[0] <= target_h:
            lo = mid
        else:
            hi = mid
    # 向下量化到 5% 步进：保证量化后一定仍放得下，且与 PowerPoint 的取值习惯一致
    steps = int(lo / SCALE_STEP)
    quantized = max(MIN_SCALE, steps * SCALE_STEP)
    return quantized, info


# ------------------------------------------------------------------ 写回 XML
def write_norm_autofit(tf, scale: float, ln_spc_reduction: int = 0) -> None:
    bodyPr = tf._txBody.find(qn("a:bodyPr"))
    if bodyPr is None:
        return
    for tag in ("a:normAutofit", "a:spAutoFit", "a:noAutofit"):
        for el in bodyPr.findall(qn(tag)):
            bodyPr.remove(el)
    el = etree.SubElement(bodyPr, qn("a:normAutofit"))
    el.set("fontScale", str(int(round(scale * 100000))))
    el.set("lnSpcReduction", str(int(ln_spc_reduction)))


def _iter_frames(prs, include_cells: bool = False, include_sp_autofit: bool = False):
    """
    遍历可处理的文本框。

    include_cells=False：表格单元格默认跳过——PowerPoint 里表格行会随内容自动增高，
    对单元格写 fontScale 语义不确定，交由行高自适应处理更稳。
    include_sp_autofit=False：`spAutoFit`（形状随文字长高）的框不会溢出，无需缩排；
    python-pptx 的 add_textbox 默认就是 spAutoFit，必须区分开，否则会误判。
    """
    for slide in prs.slides:
        for shape in slide.shapes:
            for item in _walk(shape):
                if item.has_text_frame and item.text_frame.text.strip():
                    tf = item.text_frame
                    is_grow = tf.auto_size is not None and \
                        "SHAPE_TO_FIT_TEXT" in str(tf.auto_size)
                    if not (is_grow and not include_sp_autofit):
                        yield item, tf
                if include_cells and getattr(item, "has_table", False):
                    for row in item.table.rows:
                        for cell in row.cells:
                            if cell.text_frame.text.strip():
                                yield cell, cell.text_frame


def _walk(shape):
    """递归展开组合形状。"""
    yield shape
    if shape.shape_type == 6 or getattr(shape, "shapes", None) is not None:  # GROUP
        try:
            for sub in shape.shapes:
                yield from _walk(sub)
        except Exception:
            pass


def autofit_presentation(prs, max_scale: float = 1.0,
                         min_scale: float = MIN_SCALE,
                         include_cells: bool = False,
                         metrics: "FontMetrics" = None) -> List[dict]:
    """就地修改：对需要缩放的文本框写入 fontScale。返回报告。

    metrics 可注入（测试用），默认使用真实字体度量。
    """
    metrics = metrics or FontMetrics()
    report: List[dict] = []

    for shape, tf in _iter_frames(prs, include_cells=include_cells):
        try:
            scale, info = compute_scale(tf, shape, metrics)
            scaled = min(max(scale, min_scale), max_scale)
            if scaled < 0.999:
                write_norm_autofit(tf, scaled)
            else:
                write_norm_autofit(tf, 1.0)
            report.append({
                "shape_id": getattr(shape, "shape_id", None),
                "name": getattr(shape, "name", ""),
                "text": (tf.text or "")[:40].replace("\n", " / "),
                "need_h_pt": round(info["need_h"], 1),
                "avail_h_pt": round(info["avail_h"], 1),
                "avail_w_pt": round(info["avail_w"], 1),
                "lines": info["lines"],
                "scale": round(scaled, 4),
            })
        except Exception as exc:                     # 单个形状失败不影响整体
            report.append({"shape_id": getattr(shape, "shape_id", None),
                           "name": getattr(shape, "name", ""),
                           "error": str(exc)})
    return report
