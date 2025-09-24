# pyuno 日志系统使用说明

## 概述

pyuno项目已集成完整的日志系统，提供详细的执行日志、错误追踪和性能监控功能。日志系统支持多级别记录、彩色输出、文件存储和子进程日志分离。

## 日志配置

### 1. 日志配置文件

- **文件**: `logger_config.py`
- **功能**: 统一的日志配置模块
- **特性**: 
  - 支持彩色控制台输出
  - 自动创建日志目录
  - 时间戳格式化
  - 敏感信息过滤

### 2. 日志级别

- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

## 使用方法

### 1. 主进程日志

```python
from logger_config import setup_default_logging, get_logger

# 设置默认日志（自动创建logs目录）
logger = setup_default_logging()

# 记录不同级别的日志
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
```

### 2. 子进程日志

```python
from logger_config import setup_subprocess_logging, get_logger

# 设置子进程日志（仅文件输出）
log_file = "logs/subprocess.log"
logger = setup_subprocess_logging(log_file)

# 获取子进程日志记录器
logger = get_logger("pyuno.subprocess")
```

### 3. 函数调用日志

```python
from logger_config import log_function_call, log_execution_time
from datetime import datetime

def my_function(param1, param2):
    start_time = datetime.now()
    
    # 记录函数调用
    log_function_call(logger, "my_function", param1=param1, param2=param2)
    
    # 函数逻辑...
    
    # 记录执行时间
    log_execution_time(logger, "my_function", start_time)
```

## 文件结构

```
pyuno/
├── temp/                           # 临时文件目录
│   ├── load_ppt_result_abc123.json # 生成的JSON文件
│   └── ...
├── logs/                           # 日志文件目录
│   ├── pyuno_20241201_143022.log   # 主进程日志
│   ├── subprocess.log              # 子进程日志
│   └── ...
├── logger_config.py                # 日志配置
├── pyuno_controller.py             # 主控制器（已集成日志）
├── load_ppt.py                     # PPT加载器（已集成日志）
├── read_ppt_page_uno.py           # PPT读取器（已集成日志）
├── start_libreoffice_service.py   # LibreOffice服务启动器
├── .gitignore                      # Git忽略文件
└── README_LOGGING.md              # 本文档
```

## 已集成日志的模块

### 1. pyuno_controller.py

- **功能**: 主控制器，协调整个PPT处理流程
- **日志特性**:
  - 记录函数调用参数
  - 监控子进程执行状态
  - 记录文件大小和处理统计
  - 详细的错误追踪
- **临时文件**: 生成的JSON文件存放在 `temp/` 目录

### 2. load_ppt.py

- **功能**: PPT文件加载和内容提取
- **日志特性**:
  - 记录LibreOffice连接状态
  - 监控页面处理进度
  - 记录文本片段统计
  - 子进程专用日志

### 3. read_ppt_page_uno.py

- **功能**: 单页PPT文本内容读取
- **日志特性**:
  - 记录文本框处理过程
  - 监控文本片段提取
  - 记录属性转换过程
  - 详细的调试信息

### 4. start_libreoffice_service.py

- **功能**: LibreOffice服务启动器
- **日志特性**:
  - 记录服务启动过程
  - 监控端口状态
  - 记录进程管理
  - 优雅关闭处理

## 日志输出示例

### 控制台输出（彩色）

```
2024-12-01 14:30:22 - pyuno - INFO - pyuno_controller:85 - 开始处理PPT: F:/pptxTest/pyuno/abc.pptx
2024-12-01 14:30:22 - pyuno - INFO - run_load_ppt_subprocess:25 - 使用temp目录: F:\pptxTest\pyuno\temp
2024-12-01 14:30:22 - pyuno - INFO - run_load_ppt_subprocess:26 - 输出文件路径: F:\pptxTest\pyuno\temp\load_ppt_result_abc123.json
2024-12-01 14:30:23 - pyuno - INFO - run_load_ppt_subprocess:45 - 子进程执行成功
2024-12-01 14:30:23 - pyuno - INFO - pyuno_controller:120 - 成功读取PPT内容，共 5 页，23 个文本片段
```

### 文件输出（详细）

```
2024-12-01 14:30:22 - pyuno - INFO - pyuno_controller:85 - 开始处理PPT: F:/pptxTest/pyuno/abc.pptx
2024-12-01 14:30:22 - pyuno - DEBUG - run_load_ppt_subprocess:15 - 调用函数: run_load_ppt_subprocess 参数: {'ppt_path': 'F:/pptxTest/pyuno/abc.pptx'}
2024-12-01 14:30:22 - pyuno - INFO - run_load_ppt_subprocess:25 - 使用temp目录: F:\pptxTest\pyuno\temp
2024-12-01 14:30:22 - pyuno - DEBUG - run_load_ppt_subprocess:30 - 当前工作目录: F:\pptxTest\pyuno
2024-12-01 14:30:22 - pyuno - DEBUG - run_load_ppt_subprocess:31 - load_ppt脚本路径: F:\pptxTest\pyuno\load_ppt.py
```

## 临时文件管理

### 1. temp目录

- **位置**: `pyuno/temp/`
- **用途**: 存放生成的JSON文件和其他临时文件
- **特点**: 
  - 自动创建（如果不存在）
  - 使用唯一文件名避免冲突
  - 默认自动清理（可配置保留）

### 2. 文件命名规则

```
load_ppt_result_{8位随机字符串}.json
```

例如：`load_ppt_result_a1b2c3d4.json`

### 3. 清理策略

- **默认**: 处理完成后自动删除临时文件
- **调试模式**: 可注释清理代码保留文件
- **手动清理**: 定期清理temp目录

## 故障排查

### 1. 子进程超时问题

查看日志中的详细错误信息：

```bash
# 检查主进程日志
tail -f logs/pyuno_*.log

# 检查子进程日志
tail -f logs/subprocess.log

# 检查临时文件
ls -la temp/
```

### 2. LibreOffice连接问题

```bash
# 启动LibreOffice服务
python start_libreoffice_service.py

# 检查服务状态
netstat -an | findstr 2002
```

### 3. 文件权限问题

确保目录有写入权限：

```bash
# Windows
icacls temp /grant Users:F
icacls logs /grant Users:F

# Linux/Mac
chmod 755 temp logs
```

### 4. 临时文件问题

```bash
# 检查temp目录
ls -la temp/

# 清理临时文件
rm -rf temp/*

# 重新创建目录
mkdir -p temp
```

## 自定义配置

### 1. 修改日志级别

```python
# 设置DEBUG级别（更详细）
logger = setup_default_logging(level="DEBUG")

# 设置WARNING级别（仅警告和错误）
logger = setup_default_logging(level="WARNING")
```

### 2. 自定义日志文件

```python
# 指定自定义日志文件
logger = setup_logger(
    name="my_app",
    level="INFO",
    log_file="my_app.log",
    console_output=True
)
```

### 3. 禁用控制台输出

```python
# 仅文件输出
logger = setup_logger(
    name="file_only",
    level="INFO",
    log_file="file_only.log",
    console_output=False
)
```

### 4. 保留临时文件

在 `pyuno_controller.py` 中注释掉清理代码：

```python
finally:
    # 注释掉下面的代码以保留临时文件
    # try:
    #     if os.path.exists(output_file):
    #         os.remove(output_file)
    #         logger.info(f"已删除临时文件: {output_file}")
    # except Exception as e:
    #     logger.error(f"删除临时文件失败: {str(e)}")
    pass
```

## 最佳实践

1. **合理使用日志级别**: 
   - DEBUG: 开发调试时使用
   - INFO: 正常流程信息
   - WARNING: 需要注意的情况
   - ERROR: 错误但不致命
   - CRITICAL: 严重错误

2. **敏感信息保护**: 
   - 自动过滤密码、密钥等敏感信息
   - 避免记录完整的文件路径

3. **性能考虑**: 
   - 大量DEBUG日志可能影响性能
   - 生产环境建议使用INFO级别

4. **文件管理**: 
   - 定期清理temp和logs目录
   - 避免临时文件堆积
   - 使用.gitignore忽略临时文件

## 常见问题

### Q: 日志文件不生成？
A: 检查logs目录权限，确保有写入权限。

### Q: 控制台没有彩色输出？
A: Windows控制台需要支持ANSI颜色，或者使用Windows Terminal。

### Q: 子进程日志为空？
A: 确保子进程正确导入了logger_config模块。

### Q: 日志文件过大？
A: 调整日志级别，定期清理旧日志文件。

### Q: temp目录文件不清理？
A: 检查pyuno_controller.py中的清理代码是否被注释。

### Q: 临时文件冲突？
A: 使用唯一文件名，避免并发处理时的文件冲突。 