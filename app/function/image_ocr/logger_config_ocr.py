import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 创建日志目录 - 使用绝对路径
current_dir = Path(__file__).parent
log_dir = current_dir / "logs"
log_dir.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"

def setup_logger(name: str, level: str = "INFO", log_to_file: bool = True, log_to_console: bool = True):
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否记录到文件
        log_to_console: 是否输出到控制台
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(DETAILED_FORMAT)
    

    
    # 文件处理器 - 可选
    if log_to_file:
        try:
            # 按日期创建日志文件
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = log_dir / f"{name}_{today}.log"
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # 如果文件日志失败，至少确保控制台日志可用
            print(f"警告: 无法创建文件日志: {e}")
    
    return logger

def get_logger(name: str = "ocr_system"):
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        logging.Logger: 日志记录器
    """
    return setup_logger(name)

# 创建默认日志记录器
default_logger = get_logger("ocr_system")
