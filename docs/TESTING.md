# 测试策略

## 分四层，各管一件事

| 层 | 回答的问题 | 依赖 | 跑在哪 |
|---|---|---|---|
| 单元 | 数学/XML 操作对不对 | 无 | CI，秒级 |
| **保真性** | 处理前后**非文本属性**是否一致 | 无 | CI |
| **完整性 / 回填对齐** | 该翻的都翻了吗、落到对的位置了吗 | 模型 mock | CI |
| **降级行为** | 模型超时/返回垃圾时会不会崩 | 模型 mock | CI |

评测（eval）不在这个范围里——它回答"译得好不好"，需要真实模型和统计指标，
见后文区别。

## 为什么保真性是最重要的一层

翻译错了用户能看出来；**版式坏了直接不可用**。所以核心不变量是：

- `ppt/theme/*`、`ppt/slideMasters/*`、`ppt/slideLayouts/*`、`ppt/media/*`
  的 part 哈希**前后完全相同**
- 每个叶子形状的 `(left, top, width, height)` 完全不变
- 每个 run 的颜色子树签名在"翻译回填"后不变
- 文本确实变了（防止空跑通过）

这些断言跑在 `tests/test_fidelity.py`，样本由 `tests/fixtures/builders.py`
在 tmp 目录即时生成——**不提交任何二进制 pptx**，样本本身也可 review。

## 模型一律 mock

`tests/test_translation_pipeline.py` 用一个假的 `translate_async` 替换网络调用，
可以精确构造：正常返回、只返回一部分、返回多余 ID、抛异常（429/超时）。

不触网 → 不花钱、结果确定、可以在 CI 上跑。

## 覆盖率只对核心模块设门槛

```bash
pytest --cov --cov-report=
coverage report --include="app/function/text_autofit.py,app/function/color_fidelity.py" --fail-under=80
```

当前：`text_autofit.py` 90%、`color_fidelity.py` 82%。
Web 路由、日志等脚手架模块不设门槛——它们不是这个项目的核心价值。

## 测试过程中发现的两个真实缺陷（已用 xfail 钉住）

### 1. 普通文本框没有被收集，只收集了表格

`page_based_translation.py:82-101` 里收集文本框的整段代码被注释掉了，
`collect_slide_paragraphs()` 实际只返回表格单元格。

验证：

```
收集到的段落数: 2
  type=table  text='Header A'
  type=table  text='Header B'      ← 普通文本框完全没出现
```

对应用例 `test_collect_includes_textbox_paragraphs`，标记为
`xfail(strict=True)`：修好后会变成 XPASS，强制移除标记。

### 2. 完全相同的两段文字只会翻译一段

`match_translations_to_paragraphs_precise` 用 `paragraphs.index(para)` 定位，
而 `ParagraphInfo` 是 dataclass、默认生成 `__eq__`，所以两段内容相同的段落
会命中同一个索引 → 只产出一个匹配。

同一页出现两次相同句子时（页脚、重复标题很常见），其中一处会保持原文。

对应用例 `test_duplicate_paragraphs_each_get_translation`，同样 `xfail(strict=True)`。

## 测试 ≠ 评测

| | 测试 | 评测 |
|---|---|---|
| 问题 | 会不会坏 | 效果好不好 |
| 判定 | 确定性断言 | 概率性指标 |
| 输入 | 合成 fixture | 真实脱敏文档 |
| 频率 | 每次提交 | 改 prompt / 换模型 |

评测指标建议：术语一致率、回填成功率、破版率、每页耗时与 token 消耗。
