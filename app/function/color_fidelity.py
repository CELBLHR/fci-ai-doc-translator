# -*- coding: utf-8 -*-
"""
颜色保真：不依赖 LibreOffice 的颜色备份/恢复 + 主题色解析。

两个核心问题
-----------
1. 翻译回填时如果重建了 run，颜色属性会丢；用 python-pptx 的 `font.color.theme_color`
   恢复还会丢掉 lumMod/lumOff 这类修饰符，导致颜色变样。
   → 解法：备份/恢复 `<a:rPr>` 的整棵子树，字节级无损。

2. `python-pptx` 对主题色只给出槽位（ACCENT_1），给不出最终 RGB。
   → 解法：自己解析 theme 的 clrScheme + clrMap + 修饰符（纯计算，无需渲染器）。
"""
from __future__ import annotations

import colorsys
import copy
import hashlib
import json
import zipfile
from typing import Dict, Optional, Tuple

from lxml import etree
from pptx.oxml.ns import qn

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"

# 颜色相关的子元素；恢复时整棵塞回去
COLOR_TAGS = ("a:solidFill", "a:gradFill", "a:pattFill",
              "a:highlight", "a:uFill", "a:effectLst")

RGB = Tuple[int, int, int]


# ------------------------------------------------------------ 快照 / 恢复
def _sig(el) -> str:
    """规范化序列化：只保留标签、属性、子节点，忽略命名空间声明噪音。"""
    def walk(node):
        return [etree.QName(node).localname,
                sorted((k, v) for k, v in node.attrib.items()),
                [walk(c) for c in node]]
    return hashlib.sha1(
        json.dumps(walk(el), ensure_ascii=False,
                   sort_keys=True).encode()).hexdigest()


def snapshot_rpr(run) -> Dict[str, object]:
    """备份 run 的 rPr 属性与颜色子树。"""
    rPr = run._r.find(qn("a:rPr"))
    if rPr is None:
        return {"attrs": {}, "children": {}, "sig": None}
    attrs = dict(rPr.attrib)
    children = {}
    for tag in COLOR_TAGS:
        el = rPr.find(qn(tag))
        if el is not None:
            children[tag] = copy.deepcopy(el)
    return {"attrs": attrs, "children": children, "sig": _sig(rPr)}


def restore_rpr(run, snap: Dict[str, object]) -> None:
    """把备份的 rPr 原样恢复（保留翻译后写入的 lang）。只增改不删除其他属性。"""
    if not snap or not snap.get("attrs") and not snap.get("children"):
        return
    rPr = run._r.get_or_add_rPr()
    for k, v in (snap.get("attrs") or {}).items():
        if k == "lang":          # 语言标记保留译文侧设置
            continue
        rPr.set(k, v)
    for tag, el in (snap.get("children") or {}).items():
        for old in rPr.findall(qn(tag)):
            rPr.remove(old)
        # 颜色元素必须排在 fill 之后的合法位置：直接 append 即可被 PowerPoint 接受
        rPr.append(copy.deepcopy(el))


def rpr_signature(run) -> Optional[str]:
    rPr = run._r.find(qn("a:rPr"))
    return _sig(rPr) if rPr is not None else None


def color_signature(run) -> Optional[str]:
    """只针对"颜色相关子树"算签名——判断保真用这个，避免 lang 等无关属性干扰。"""
    rPr = run._r.find(qn("a:rPr"))
    if rPr is None:
        return None
    parts = {}
    for tag in COLOR_TAGS:
        el = rPr.find(qn(tag))
        if el is not None:
            parts[tag] = _sig(el)
    return hashlib.sha1(
        json.dumps(parts, sort_keys=True).encode()).hexdigest() if parts else "none"


# ------------------------------------------------------------ 主题色解析
def _hex(c: str) -> RGB:
    c = (c or "000000").strip().lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def load_theme(zf: zipfile.ZipFile, theme_part: str = "ppt/theme/theme1.xml"
               ) -> Dict[str, RGB]:
    """读取主题的 clrScheme：dk1/lt1/dk2/lt2/accent1..6/hlink/folHlink。"""
    root = etree.fromstring(zf.read(theme_part))
    scheme = root.find(f".//{{{A_NS}}}clrScheme")
    out: Dict[str, RGB] = {}
    if scheme is None:
        return out
    for child in scheme:
        name = etree.QName(child).localname
        srgb = child.find(f"{{{A_NS}}}srgbClr")
        sysclr = child.find(f"{{{A_NS}}}sysClr")
        if srgb is not None:
            out[name] = _hex(srgb.get("val"))
        elif sysclr is not None:
            out[name] = _hex(sysclr.get("lastClr"))
    return out


def load_clr_map(zf: zipfile.ZipFile, slide_part: str) -> Dict[str, str]:
    """
    bg1/tx1/... → 主题槽位名。
    幻灯片可用 clrMapOvr 覆盖；否则沿用 slideMaster 的 clrMap。
    """
    root = etree.fromstring(zf.read(slide_part))
    override = root.find(f".//{{{A_NS}}}overrideClrMapping")
    if override is not None:
        return dict(override.attrib)

    # 找到对应 slideMaster
    master = None
    for rel in root.findall(f".//{{{P_NS}}}sldMasterId"):
        rid = rel.get(f"{{{A_NS.replace('drawingml/2006/main', 'officeDocument/2006/relationships')}}}id")
        if rid:
            try:
                target = rel.getparent()
            except Exception:
                target = None
    # 简化：直接取包内第一个 slideMaster（演示用途足够；生产按关系解析）
    for name in zf.namelist():
        if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml"):
            mroot = etree.fromstring(zf.read(name))
            cm = mroot.find(f"{{{P_NS}}}clrMap")
            if cm is not None:
                master = dict(cm.attrib)
            break
    return master or {}


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def _apply_mods(rgb: RGB, mods: Dict[str, int]) -> RGB:
    """按 OOXML 修饰符调整颜色。

    - lumMod / lumOff：作用在 HSL 亮度通道上（Office 实测与 gamma 空间一致）
    - shade / tint   ：作用在线性 RGB 空间（Office 实测：先做 sRGB 线性化再运算）
    """
    r, g, b = [c / 255.0 for c in rgb]

    if "lumMod" in mods or "lumOff" in mods:
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if "lumMod" in mods:
            l *= mods["lumMod"] / 100000.0
        if "lumOff" in mods:
            l += mods["lumOff"] / 100000.0
        l = min(max(l, 0.0), 1.0)
        r, g, b = colorsys.hls_to_rgb(h, l, s)

    if "shade" in mods:
        f = mods["shade"] / 100000.0
        lin = [_srgb_to_linear(c) * f for c in (r, g, b)]
        r, g, b = [_linear_to_srgb(c) for c in lin]

    if "tint" in mods:
        f = mods["tint"] / 100000.0
        lin = [_srgb_to_linear(c) * f + (1 - f) for c in (r, g, b)]
        r, g, b = [_linear_to_srgb(c) for c in lin]

    return tuple(int(round(min(max(c, 0.0), 1.0) * 255)) for c in (r, g, b))


def resolve_scheme_color(scheme_el, theme: Dict[str, RGB],
                         clr_map: Dict[str, str]) -> Optional[RGB]:
    """把一个 <a:schemeClr> 元素解析成最终 RGB。"""
    val = scheme_el.get("val")
    if not val:
        return None
    slot = clr_map.get(val, val)        # bg1 → lt1 / dk1 ...
    base = theme.get(slot) or theme.get(val)
    if base is None:
        return None
    mods = {}
    for child in scheme_el:
        name = etree.QName(child).localname
        if name in ("lumMod", "lumOff", "shade", "tint"):
            try:
                mods[name] = int(child.get("val"))
            except (TypeError, ValueError):
                pass
    return _apply_mods(base, mods)


def resolve_run_color(run, theme, clr_map) -> Optional[Dict[str, object]]:
    """返回 run 的颜色信息：显式 RGB 或解析后的主题色。"""
    rPr = run._r.find(qn("a:rPr"))
    if rPr is None:
        return None
    fill = rPr.find(qn("a:solidFill"))
    if fill is None:
        return None
    srgb = fill.find(qn("a:srgbClr"))
    if srgb is not None:
        return {"kind": "rgb", "rgb": _hex(srgb.get("val"))}
    scheme = fill.find(qn("a:schemeClr"))
    if scheme is not None:
        return {"kind": "scheme", "slot": scheme.get("val"),
                "rgb": resolve_scheme_color(scheme, theme, clr_map)}
    return None


# ------------------------------------------------------------ 一致性校验
def collect_run_signatures(pptx_path: str):
    """收集每个 run 的 rPr 签名，用于前后对比。返回 [(slide, shape, text, sig)]。"""
    from pptx import Presentation
    prs = Presentation(pptx_path)
    rows = []
    for si, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for pi, para in enumerate(shape.text_frame.paragraphs):
                for ri, run in enumerate(para.runs):
                    rows.append((si, shape.name, f"p{pi}r{ri}", run.text,
                                 rpr_signature(run)))
    return rows
