# 段落层级翻译功能使用指南

## 📋 概述

本项目已升级支持段落层级的PPT翻译功能。新版本在原有文本框级别的基础上，增加了段落层级，使翻译更加精确和灵活。

## 🏗️ 新的数据结构

### 原结构 vs 新结构

**原结构：**
```
PPT → 页面 → 文本框 → 文本片段
```

**新结构：**
```
PPT → 页面 → 文本框 → 段落 → 文本片段
```

### JSON数据格式变化

**新的JSON结构示例：**
```json
{
  "presentation_path": "test.pptx",
  "statistics": {
    "total_pages": 2,
    "total_boxes": 3,
    "total_paragraphs": 5,
    "total_fragments": 12
  },
  "pages": [
    {
      "page_index": 0,
      "total_boxes": 2,
      "total_paragraphs": 3,
      "text_boxes": [
        {
          "box_index": 0,
          "box_id": "textbox_0",
          "box_type": "text",
          "total_paragraphs": 2,
          "paragraphs": [
            {
              "paragraph_index": 0,
              "paragraph_id": "para_0_0",
              "text_fragments": [
                {
                  "fragment_id": "frag_0_0_0",
                  "text": "段落1文本",
                  "color": 0,
                  "underline": false,
                  "bold": true,
                  "escapement": 0,
                  "font_size": 24.0
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## 🔄 翻译流程变化

### 1. 文本提取阶段

- **提取单位**：从文本框级别细化到段落级别
- **输出格式**：每个段落独立提取，保持段落内的格式完整性

### 2. 翻译API调用

**新的输入格式：**
```
第1页内容：

【文本框1-段落1】
【文本框1-段落1内的原始文本】

【文本框1-段落2】
【文本框1-段落2内的原始文本】

【文本框2-段落1】
【文本框2-段落1内的原始文本】
```

**新的输出格式：**
```json
[
  {
    "box_index": 1,
    "paragraph_index": 1,
    "source_language": "Hello[block]World",
    "target_language": "你好[block]世界"
  },
  {
    "box_index": 1,
    "paragraph_index": 2,
    "source_language": "This is[block]a test",
    "target_language": "这是[block]一个测试"
  }
]
```

### 3. 结果映射

- **映射键格式**：`{box_index}_{paragraph_index}`（如 "1_1", "1_2", "2_1"）
- **映射精度**：精确到段落级别，保持段落内格式一致性

## 🚀 快速开始

### 1. 环境准备

```bash
# 启动LibreOffice服务
soffice --headless --accept="socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"

# 设置环境变量（可选）
export DASHSCOPE_API_KEY="your_api_key"
export LIBREOFFICE_PYTHON="C:/Program Files/LibreOffice/program/python.exe"
export SOFFICE_PATH="C:/Program Files/LibreOffice/program/soffice.exe"
```

### 2. 运行测试

```bash
# 运行完整测试套件
python test_paragraph_translation.py

# 测试指定PPT文件
python test_paragraph_translation.py your_presentation.pptx

# 测试段落结构加载
python test_paragraph_structure.py your_presentation.pptx
```

### 3. 使用主程序

```python
from pyuno_controller import pyuno_controller

result = pyuno_controller(
    presentation_path="your_file.pptx",
    stop_words_list=[],
    custom_translations={},
    select_page=[],
    source_language='en',
    target_language='zh',
    bilingual_translation='paragraph'
)

if result:
    print(f"翻译成功，输出文件：{result}")
else:
    print("翻译失败")
```

## 📊 新功能特性

### 1. 段落级别翻译

- **精确分割**：按换行符自动识别段落
- **格式保留**：保持段落内的字体格式
- **独立翻译**：每个段落独立处理，避免上下文混乱

### 2. 增强的统计信息

```json
{
  "translation_metadata": {
    "total_pages_translated": 2,
    "successful_pages": 2,
    "failed_pages": 0,
    "total_fragments_updated": 15,
    "total_box_paragraphs_processed": 8,
    "translation_timestamp": "2025-01-15T10:30:00",
    "structure_version": "with_paragraphs"
  }
}
```

### 3. 验证和质量控制

- **覆盖率检查**：验证翻译覆盖率
- **数量匹配**：检查片段数量一致性
- **结构验证**：验证段落结构完整性

## 🔧 API参考

### 主要函数

#### `extract_texts_for_translation(ppt_data)`
```python
"""
从PPT数据中提取文本段落
Returns:
    tuple: (text_boxes_data, fragment_mapping)
    - text_boxes_data: 按段落分组的文本数据
    - fragment_mapping: 片段ID映射
"""
```

#### `format_page_text_for_translation(text_boxes_data, page_index)`
```python
"""
格式化页面文本用于翻译API
Returns:
    str: 格式化后的文本（包含段落标识）
"""
```

#### `translate_pages_by_page(text_boxes_data, source_lang, target_lang)`
```python
"""
按页翻译文本内容
Returns:
    dict: {page_index: translation_result}
"""
```

#### `map_translation_results_back(ppt_data, translation_results, text_boxes_data)`
```python
"""
将翻译结果映射回PPT数据结构
Returns:
    dict: 包含翻译的PPT数据
"""
```

### 数据结构

#### 文本框段落数据结构
```python
{
    'page_index': 0,
    'box_index': 0,
    'box_id': 'textbox_0',
    'paragraph_index': 0,
    'paragraph_id': 'para_0_0',
    'texts': ['文本片段1', '文本片段2'],
    'combined_text': '文本片段1[block]文本片段2',
    'global_index': 0
}
```

#### 翻译结果结构
```python
{
    page_index: {
        'translated_fragments': {
            'box_paragraph_key': ['翻译片段1', '翻译片段2']
        },
        'box_paragraph_count': 5,
        'box_count': 2
    }
}
```

## 🧪 测试指南

### 测试类型

1. **单元测试**：
   - 文本提取功能
   - 格式化功能
   - 翻译结果解析
   - 结果映射功能

2. **集成测试**：
   - 完整翻译流程
   - 子进程调用
   - 文件I/O操作

3. **验证测试**：
   - 数据结构完整性
   - 翻译质量检查
   - 性能测试

### 运行测试

```bash
# 完整测试套件
python test_paragraph_translation.py

# 指定PPT文件测试
python test_paragraph_translation.py path/to/your/test.pptx

# 段落结构测试
python test_paragraph_structure.py path/to/your/test.pptx
```

### 测试报告

测试完成后会生成详细报告：
- 测试时间和耗时
- 成功/失败统计
- 详细错误信息
- 覆盖率分析

## 🐛 故障排除

### 常见问题

#### 1. LibreOffice服务问题
```bash
# 检查服务状态
ps aux | grep soffice

# 重启服务
pkill soffice
soffice --headless --accept="socket,host=localhost,port=2002;urp;"
```

#### 2. 翻译API问题
- 检查API密钥设置
- 验证网络连接
- 查看API调用日志

#### 3. 段落识别问题
- 检查PPT中的换行符
- 验证文本框内容
- 查看提取日志

### 日志分析

主要日志位置：
- `logs/subprocess.log` - 子进程日志
- `test_temp/test_report_*.json` - 测试报告
- 控制台输出 - 实时日志

## 📈 性能优化

### 建议

1. **批量处理**：按页面批量调用翻译API
2. **缓存机制**：缓存重复的翻译结果
3. **并行处理**：多页面并行翻译（未来版本）
4. **内存管理**：及时清理临时文件

### 限制

- 单次翻译建议不超过50页
- 单个文本框段落不超过1000字符
- API调用频率限制需要注意

## 🔄 版本兼容性

### 向后兼容

- 保留原有的函数接口
- 支持旧版本JSON格式读取
- 提供兼容性函数

### 迁移指南

从旧版本升级：
1. 备份现有数据
2. 更新代码文件
3. 运行测试验证
4. 逐步迁移数据

## 📞 支持

如遇问题，请：
1. 查看日志文件
2. 运行测试脚本诊断
3. 检查环境配置
4. 参考故障排除指南

---

*最后更新：2025-01-15*
