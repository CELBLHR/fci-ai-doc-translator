#!/usr/bin/env python3
"""
测试文件路径和目录结构
"""

import os
import sys
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_directory_structure():
    """测试目录结构"""
    try:
        # 获取当前工作目录
        current_dir = os.getcwd()
        logger.info(f"当前工作目录: {current_dir}")
        
        # 检查项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"项目根目录: {project_root}")
        
        # 检查上传目录
        upload_dir = os.path.join(project_root, 'app', 'uploads')
        logger.info(f"上传目录: {upload_dir}")
        
        # 检查PDF相关目录
        pdf_upload_dir = os.path.join(upload_dir, 'pdf_uploads')
        pdf_output_dir = os.path.join(upload_dir, 'pdf_outputs')
        
        logger.info(f"PDF上传目录: {pdf_upload_dir}")
        logger.info(f"PDF输出目录: {pdf_output_dir}")
        
        # 创建目录（如果不存在）
        os.makedirs(pdf_upload_dir, exist_ok=True)
        os.makedirs(pdf_output_dir, exist_ok=True)
        
        logger.info(f"PDF上传目录是否存在: {os.path.exists(pdf_upload_dir)}")
        logger.info(f"PDF输出目录是否存在: {os.path.exists(pdf_output_dir)}")
        
        # 在目录中创建测试文件
        test_file_path = os.path.join(pdf_output_dir, 'test_file.txt')
        with open(test_file_path, 'w') as f:
            f.write('This is a test file.')
        
        logger.info(f"测试文件已创建: {test_file_path}")
        logger.info(f"测试文件是否存在: {os.path.exists(test_file_path)}")
        logger.info(f"测试文件大小: {os.path.getsize(test_file_path)} 字节")
        
        # 列出目录中的文件
        files_in_output_dir = os.listdir(pdf_output_dir)
        logger.info(f"PDF输出目录中的文件: {files_in_output_dir}")
        
        # 清理测试文件
        os.remove(test_file_path)
        logger.info("测试文件已清理")
        
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    logger.info("开始测试文件路径和目录结构")
    success = test_directory_structure()
    if success:
        logger.info("文件路径和目录结构测试通过")
        print("SUCCESS: 文件路径和目录结构测试通过")
    else:
        logger.error("文件路径和目录结构测试失败")
        print("ERROR: 文件路径和目录结构测试失败")