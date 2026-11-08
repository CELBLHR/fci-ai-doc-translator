# 去掉 LibreOffice：无渲染器的版式保真

本项目的翻译链路原本有两个环节依赖 LibreOffice 的格式转换：

1. **文本框自适应**——要触发渲染器才会计算"溢出时缩排"的缩放比
2. **字体颜色提取**——主题色在 `python-pptx` 里只给得出槽位，给不出实际 RGB

这两个环节都已改为纯 Python 实现，**不再需要 LibreOffice，也不再有整包重导出的风险**。

---

## 一、文本框自适应（`app/function/text_autofit.py`）

### 为什么原来必须转一次格式

PowerPoint 的"溢出时缩排"真值写在 OOXML 里：

```xml
<a:bodyPr><a:normAutofit fontScale="62500" lnSpcReduction="0"/></a:bodyPr>
```

`fontScale` 单位是 **1/1000 百分比**（`62500` = 62.5%）。而 `python-pptx` 设
`text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` 时只会写一个**空的**
`<a:normAutofit/>`，没有 `fontScale`。这个数字原本由渲染器算——所以只好跑一次
LibreOffice 转换，让它把值补上；而 LO 是整包反序列化再序列化，主题、背景、
SmartArt 等它没完整建模的部分就会丢。

### 现在的做法

自己算这个数字，直接写入：

```
1. 可用宽度 = 框宽 - 左右内边距（组内形状会累乘 grpSp 的 chExt→ext 缩放）
2. 用字体 advance width 断行：CJK 逐字断，拉丁按空格断
3. 估算总高度 = Σ(行数 × 行高) + 段前段后
4. 溢出时二分搜索 scale ∈ [0.25, 1.0]，按 5% 步进向下量化
5. 写回 <a:normAutofit fontScale="..." lnSpcReduction="0"/>
```

只修改 `<a:bodyPr>` 的子节点，**不触碰任何其他 part**。

### 实测校准（对照 PowerPoint COM）

用 PowerPoint 12.0 COM 设置 `TextFrame2.AutoSize = msoAutoSizeTextToShape`，
读出它自己算的 `fontScale` 作为基准。校准过程中发现两个关键点：

| 发现 | 说明 |
|---|---|
| **行高固定是 `1.2 × 字号`** | 不是字体自身的 hhea 度量。初版用 hhea 导致高度估算系统性偏大 10.4% |
| **PowerPoint 同时用 `fontScale` 和 `lnSpcReduction`** | 它还按 10% 步进；本项目只用 `fontScale`，因此量化到 5% 更细 |

校准前后对比（8 个样本框）：

| 指标 | 校准前 | 校准后 |
|---|---|---|
| 文字高度估算误差（平均） | 15.0% | **7.3%** |
| 与 PowerPoint 完全一致的框 | 0/8 | **6/8** |
| 缩放比误差 | 平均 7.6 个百分点 | 5.0 个百分点（一个量化步进） |

剩余 2 个样本差异来自断行差一行（我的宽度测量与 PowerPoint 差约 1%），
两者都仍然"放得下"，不影响功能。

---

## 二、颜色保真（`app/function/color_fidelity.py`）

### 真正的问题不是"识别不了主题色"

`python-pptx` 其实能识别主题色：

```
color.type        : SCHEME (2)        ← 知道这是主题色
color.theme_color : ACCENT_1 (5)      ← 知道是哪个槽位
color.rgb         : AttributeError    ← 只是给不出实际 RGB
```

`color_protection.py` 里真正的 bug 是用了**不存在的枚举成员**：

```python
elif color.type == MSO_COLOR_TYPE.THEME:   # 0.6.23 没有 THEME
elif color.type == MSO_COLOR_TYPE.AUTO:    # 也没有 AUTO
```

`MSO_COLOR_TYPE` 只有 `RGB / SCHEME / PRESET / HSL`。访问不存在的成员抛
`AttributeError`，被外层 `except` 吞掉 → 函数静默返回 `None`，**主题色从未被备份**。
现已修正为 `SCHEME` / `type is None`。

### 保真用深拷贝，不用颜色 API

即使枚举写对了，用 `color.theme_color = 枚举` 恢复仍是**有损**的：

| 恢复方式 | accent1 + lumMod75 + lumOff15 |
|---|---|
| `color.theme_color = ACCENT_1` | ❌ 修饰符丢失，颜色变回 100% 亮度 |
| `copy.deepcopy(rPr子树)` | ✅ 与原始字节完全一致 |

因此备份/恢复改为直接复制 XML 子树（`a:solidFill`、`a:highlight`、`a:uFill` 等），
连"是 RGB 还是主题色"都不用判断。

### 需要实际 RGB 时，自己解析

```
theme1.xml 的 <a:clrScheme>  → dk1/lt1/dk2/lt2/accent1..6/hlink/folHlink
slide 或 master 的 <p:clrMap> → bg1/tx1/... 映射到哪个槽位（幻灯片可覆盖）
修饰符：
  lumMod / lumOff → HSL 亮度通道
  shade / tint    → 线性 RGB 空间（先做 sRGB 线性化）
```

第二行是关键：`shade` **不是**在 gamma 空间直接乘。按 gamma 空间算会得到
`#73302E`，而 PowerPoint 实际渲染是 `#993E3C`（线性化后乘 0.6 再编码回来）。

### 实测校准（对照 PowerPoint COM）

7 个样本，覆盖显式 RGB、主题色、主题色+修饰符、高亮：

| 颜色 | 本实现 | PowerPoint | |
|---|---|---|---|
| `srgbClr FF0000` | `#FF0000` | `#FF0000` | ✅ |
| `accent1` | `#4F81BD` | `#4F81BD` | ✅ |
| `accent1` + `lumMod75` + `lumOff15` | `#5686C0` | `#5686C0` | ✅ |
| `tx1`（clrMap → dk1） | `#000000` | `#000000` | ✅ |
| `accent2` + `shade60` | `#993E3C` | `#993E3C` | ✅ |
| `srgbClr 00B050` | `#00B050` | `#00B050` | ✅ |
| `bg1`（clrMap → lt1） | `#FFFFFF` | `#FFFFFF` | ✅ |

**7/7 完全一致。**

---

## 三、副作用与性能

**结构副作用**（同一份 deck，处理前后对比每个 zip part 的 sha256）：

| part | 变化 |
|---|---|
| `ppt/theme/*` | **0** |
| `ppt/slideMasters/*` | **0** |
| `ppt/slideLayouts/*` | **0** |
| `ppt/media/*` | **0** |
| `ppt/slides/*` | 仅写入 `fontScale` / 颜色恢复的部分 |

对照：LibreOffice 转换会让几乎所有 part 的哈希都变化。

**耗时**（18 个 run 的演示 deck）：

```
加载 PPT         8.8 ms
颜色快照 + 恢复   6.3 ms
autofit 计算      8.4 ms
保存             11.2 ms
─────────────────────────
合计             34.7 ms
```

LibreOffice 路径需要启动 `soffice` 进程并整包重写，是**秒级**。

---

## 四、局限

- **断行精度**：与 PowerPoint 差约 1%，边界情况下可能多断/少断一行。已用
  `WRAP_TOLERANCE = 1.02` 和 `TARGET_FILL = 0.97` 留出安全余量。
- **表格单元格默认跳过**：PowerPoint 中表格行会随内容增高，对单元格写
  `fontScale` 语义不确定，交由行高自适应处理更稳。
- **旋转文本**：目前按未旋转的框宽高估算，`vert` 竖排未特殊处理。
- **字体缺失时**：退化为"CJK 全宽 / 拉丁半宽"的估算，并偏保守。

## 五、LibreOffice 仍然需要的场景

- 旧格式 `.ppt` / `.odp` 的读取
- 必须把结果渲染成图片做视觉校验时（**只读渲染**，不允许它保存 pptx）
- SmartArt / 图表内文字的深度遍历（XML 里有，只是结构嵌套更深）

## 六、复现

```bash
pip install -r requirements-dev.txt
pytest                      # 19 个用例，覆盖 autofit 与颜色保真
```

涉及 PowerPoint 对照数据的验证脚本位于开发分支的工具目录，需要本机安装
Office 并可用 COM；CI 中不执行（仅用单元测试守护数学与结构不变量）。
