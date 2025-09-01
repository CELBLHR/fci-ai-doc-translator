#!/usr/bin/env python3
"""
调试脚本，检查PDF翻译生成的文件
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

def debug_pdf_files():
    """调试PDF翻译生成的文件"""
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"项目根目录: {project_root}")
        
        # 检查上传目录
        upload_dir = os.path.join(project_root, 'app', 'uploads')
        logger.info(f"上传目录: {upload_dir}")
        logger.info(f"上传目录是否存在: {os.path.exists(upload_dir)}")
        
        if os.path.exists(upload_dir):
            upload_subdirs = os.listdir(upload_dir)
            logger.info(f"上传目录子目录: {upload_subdirs}")
            
            # 检查PDF相关目录
            pdf_upload_dir = os.path.join(upload_dir, 'pdf_uploads')
            pdf_output_dir = os.path.join(upload_dir, 'pdf_outputs')
            
            logger.info(f"PDF上传目录: {pdf_upload_dir}")
            logger.info(f"PDF上传目录是否存在: {os.path.exists(pdf_upload_dir)}")
            
            logger.info(f"PDF输出目录: {pdf_output_dir}")
            logger.info(f"PDF输出目录是否存在: {os.path.exists(pdf_output_dir)}")
            
            # 列出PDF上传目录中的文件
            if os.path.exists(pdf_upload_dir):
                pdf_upload_files = os.listdir(pdf_upload_dir)
                logger.info(f"PDF上传目录中的文件: {pdf_upload_files}")
            
            # 列出PDF输出目录中的文件
            if os.path.exists(pdf_output_dir):
                pdf_output_files = os.listdir(pdf_output_dir)
                logger.info(f"PDF输出目录中的文件: {pdf_output_files}")
                
                # 显示每个文件的详细信息
                for file in pdf_output_files:
                    file_path = os.path.join(pdf_output_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        logger.info(f"  文件: {file}, 大小: {file_size} 字节")
            else:
                logger.error("PDF输出目录不存在")
        
        return True
        
    except Exception as e:
        logger.error(f"调试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主函数"""
    logger.info("开始调试PDF翻译生成的文件")
    
    try:
        success = debug_pdf_files()
        if success:
            logger.info("调试完成")
            print("SUCCESS: 调试完成")
            return True
        else:
            logger.error("调试失败")
            print("ERROR: 调试失败")
            return False
        
    except Exception as e:
        logger.error(f"调试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    main()