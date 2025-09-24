'''
start_libreoffice_service.py
启动LibreOffice监听服务，为pyuno模块提供UNO接口支持
'''
import subprocess
import os
import sys
import time
import signal
from .logger_config import setup_default_logging, get_logger
from dotenv import load_dotenv

load_dotenv()


def find_libreoffice_path():
    """
    查找 LibreOffice 的可执行程序路径
    支持 Windows / macOS / Linux
    """
    logger = get_logger("pyuno.service")

    # 检查环境变量
    env_path = os.environ.get('LIBREOFFICE_PATH')
    if env_path:
        soffice = os.path.join(env_path, 'program', 'soffice.exe') if sys.platform == 'win32' else os.path.join(env_path, 'program', 'soffice')
        if os.path.exists(soffice):
            logger.info(f"从环境变量找到 LibreOffice: {soffice}")
            return soffice
        else:
            logger.warning(f"环境变量LIBREOFFICE_PATH设置了，但未找到可执行文件: {soffice}")

    # Windows常见路径
    if sys.platform == 'win32':
        possible_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            r"D:\Program Files\LibreOffice\program\soffice.exe",
            r"D:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
    # macOS / Linux常见路径
    else:
        possible_paths = [
            "/usr/bin/soffice",
            "/usr/local/bin/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        ]

    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"找到 LibreOffice: {path}")
            return path

    logger.error("未找到 LibreOffice 安装路径")
    logger.error("请手动设置 LIBREOFFICE_PATH 环境变量或修改脚本中的路径")
    return None

def check_port_available(port=2002):
    """
    检查端口是否可用
    """
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def start_libreoffice_service(port=2002, headless=True):
    """
    启动LibreOffice监听服务
    
    Args:
        port: 监听端口
        headless: 是否无头模式运行
    """
    logger = get_logger("pyuno.service")
    
    # 查找LibreOffice路径
    libreoffice_path = find_libreoffice_path()
    if not libreoffice_path:
        return False
    
    # 检查端口是否可用
    if not check_port_available(port):
        logger.warning(f"端口 {port} 已被占用，可能LibreOffice服务已在运行")
        return True
    
    # 构建启动命令
    cmd = [
        libreoffice_path,
        "--headless" if headless else "",
        f"--accept=socket,host=localhost,port={port};urp;StarOffice.ComponentContext"
    ]
    
    # 过滤空字符串
    cmd = [arg for arg in cmd if arg]
    
    logger.info(f"启动LibreOffice服务: {' '.join(cmd)}")
    
    try:
        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        # 等待服务启动
        time.sleep(3)
        
        # 检查进程是否还在运行
        if process.poll() is None:
            logger.info(f"LibreOffice服务启动成功，PID: {process.pid}")
            logger.info(f"监听端口: {port}")
            return process
        else:
            stdout, stderr = process.communicate()
            logger.error(f"LibreOffice服务启动失败")
            logger.error(f"标准输出: {stdout}")
            logger.error(f"错误输出: {stderr}")
            return False
            
    except Exception as e:
        logger.error(f"启动LibreOffice服务时出错: {e}", exc_info=True)
        return False

def stop_libreoffice_service(process):
    """
    停止LibreOffice服务
    """
    logger = get_logger("pyuno.service")
    
    if process and process.poll() is None:
        logger.info(f"正在停止LibreOffice服务 (PID: {process.pid})")
        try:
            process.terminate()
            process.wait(timeout=10)
            logger.info("LibreOffice服务已停止")
        except subprocess.TimeoutExpired:
            logger.warning("服务未在10秒内停止，强制终止")
            process.kill()
            process.wait()
        except Exception as e:
            logger.error(f"停止服务时出错: {e}")

def signal_handler(signum, frame):
    """
    信号处理器，用于优雅关闭服务
    """
    logger = get_logger("pyuno.service")
    logger.info("收到停止信号，正在关闭服务...")
    sys.exit(0)

def main():
    """
    主程序入口
    """
    # 设置日志
    logger = setup_default_logging()
    logger.info("=" * 60)
    logger.info("LibreOffice服务启动器")
    logger.info("=" * 60)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动服务
    process = start_libreoffice_service(port=2002, headless=True)
    
    if not process:
        logger.error("LibreOffice服务启动失败")
        return 1
    
    try:
        logger.info("LibreOffice服务正在运行...")
        logger.info("按 Ctrl+C 停止服务")
        
        # 保持服务运行
        while True:
            if process.poll() is not None:
                logger.error("LibreOffice服务意外退出")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    finally:
        stop_libreoffice_service(process)
    
    logger.info("服务已关闭")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 