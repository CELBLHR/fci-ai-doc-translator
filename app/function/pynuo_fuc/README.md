# pyuno_fuc 目录与 pyuno_controller 总控程序说明

## 目录结构

```
app/function/pynuo_fuc/
├── api_translate_uno.py
├── change_ppt_uno.py
├── edit_ppt.py
├── load_ppt.py
├── logger_config.py
├── logs/
├── map_translation_results_back.py
├── ppt_data_utils.py
├── pyuno_controller.py
├── read_ppt_page_uno.py
├── temp/
├── temp_result/
├── test_ppt/
├── write_ppt_page_uno.py
```

---

## 设计目标

本目录为**PPT高质量自动翻译与写入的pyuno子系统**，核心目标是：
- 利用 LibreOffice UNO 接口，**高保真读取/写入PPT内容**，支持复杂格式、表格、批量处理。
- 支持**异步/批量翻译**，并将译文精准写回PPT，最大限度减少格式丢失和内容错位。
- 具备**强鲁棒性**的文本匹配机制，自动处理原文与译文的各种细微差异。
- 支持**日志追踪、调试、结果中间态保存**，便于问题定位和二次开发。

---

## 各主要文件功能说明

### 1. pyuno_controller.py（总控入口）

- **作用**：整个pyuno子系统的总调度器，负责串联各子模块，完成PPT的读取、翻译、写入、格式转换等全流程。
- **主要流程**：
  1. **run_load_ppt_subprocess**：调用 `load_ppt.py`，用LibreOffice Python读取PPT内容，生成结构化json。
  2. **翻译**：调用 `api_translate_uno.py`，对提取的文本分段翻译。
  3. **map_translation_results_back**：将翻译结果与原PPT结构对齐。
  4. **run_change_ppt_subprocess**：调用 `edit_ppt.py`，将译文写回PPT，生成新文件。
  5. **convert_odp_to_pptx**：如有需要，调用soffice命令将ODP转PPTX。
- **环境变量**：需设置 `LIBREOFFICE_PYTHON` 和 `SOFFICE_PATH`，分别指向LibreOffice的python.exe和soffice.exe。

### 2. load_ppt.py

- **作用**：用pyuno接口读取PPT内容，支持页面、文本框、表格等结构的精细提取，输出为json。
- **典型用法**：被pyuno_controller以子进程方式调用，参数为输入PPT路径和输出json路径。
- **日志**：详细记录每一步的处理状态，便于调试。

### 3. edit_ppt.py

- **作用**：用pyuno接口将翻译后的文本写回PPT，支持多种写入模式（替换、追加、逐段等），并尽量保持原有格式。
- **典型用法**：被pyuno_controller以子进程方式调用，参数为原PPT、输出PPT、翻译json、写入模式等。

### 4. ppt_data_utils.py

- **作用**：PPT数据结构的提取、转换、映射等工具函数，包括文本分段、翻译API调用、结果对齐等。

### 5. write_ppt_page_uno.py

- **作用**：负责将翻译结果精准写入PPT的每个文本框/表格，内置**相似度匹配机制**，大幅提升写入鲁棒性。
- **机制亮点**：
  - **shape定位**：先精确匹配，后用相似度兜底，防止因格式微差导致写入失败。
  - **原文-译文相似度判据**：如译文与原文高度相似（如文献引用、未翻译内容），自动跳过写入，防止误写。

### 6. api_translate_uno.py

- **作用**：负责与翻译API对接，支持批量、异步翻译，返回原文-译文映射。

### 7. logger_config.py

- **作用**：统一日志配置，支持主进程与子进程分别记录日志，便于问题追踪。

### 8. read_ppt_page_uno.py

- **作用**：pyuno接口的底层封装，负责与LibreOffice服务通信，读取PPT页面内容。

### 9. 目录说明

- `temp/`、`temp_result/`：中间文件、结果文件临时存放目录。
- `logs/`：日志文件目录。
- `test_ppt/`：测试用PPT文件目录。

---

## 日志说明

- `pyuno_xxx.log`：主程序日志，记录pyuno_controller及主流程的调度、翻译、写入等全局信息。
- `subprocess.log`：加载PPT的子进程日志，由load_ppt.py生成，详细记录PPT读取、页面解析等过程。
- `edit_ppt.log`：写PPT的子进程日志，由edit_ppt.py生成，详细记录译文写入、格式处理等过程。

所有日志文件均位于 `logs/` 目录下，便于问题追踪和调试。

---

## 运转流程（全自动PPT翻译写入）

1. **pyuno_controller.py** 作为入口，接收PPT路径、翻译参数等。
2. 调用 **load_ppt.py**，用pyuno读取PPT内容，生成结构化json。
3. 用 **api_translate_uno.py** 对json中的文本分段翻译，得到原文-译文对。
4. 用 **ppt_data_utils.py** 将翻译结果与原PPT结构对齐。
5. 调用 **edit_ppt.py**，用pyuno将译文写回PPT，支持多种写入模式。
6. 用 **write_ppt_page_uno.py**，对每个文本框/表格做精细写入，自动规避误写、漏写。
7. 如有需要，调用soffice命令将ODP转PPTX，生成最终可用的PPTX文件。
8. 全流程日志记录，所有中间结果可追溯。

---

## 特色与优势

- **高保真**：基于LibreOffice pyuno接口，最大限度还原PPT原始格式。
- **高鲁棒性**：多重相似度判据，自动兜底，极大减少人工干预。
- **易扩展**：各功能模块解耦，便于二次开发和功能增强。
- **全流程日志**：便于调试和问题定位。
- **支持大文件、批量处理**。

---

## 环境准备与运行须知

1. **安装LibreOffice**，并确保 `python.exe`、`soffice.exe` 路径正确。
2. 设置环境变量：
   - `LIBREOFFICE_PYTHON` 指向 LibreOffice 的 python.exe
   - `SOFFICE_PATH` 指向 LibreOffice 的 soffice.exe
3. 启动 LibreOffice headless 服务（如需）：
   ```
   soffice --headless --accept="socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
   ```
4. 运行主控脚本 `pyuno_controller.py`，或通过上层API调用。

---

## 交接建议

- 推荐先阅读 `pyuno_controller.py`，理解主流程。
- 各子模块均有详细注释和日志，便于定位和扩展。
- 如需对接新翻译API、支持新格式、优化匹配策略，可直接在对应模块修改。

---

如有疑问，建议先查阅日志文件，或联系原开发者。  
本README可作为pyuno子系统的快速上手与维护指南。 