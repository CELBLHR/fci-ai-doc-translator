#!/usr/bin/env python3
"""
调试脚本，验证PDF翻译和下载流程
"""

import os
import sys
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_pdf_workflow():
    """调试PDF翻译和下载流程"""
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"项目根目录: {project_root}")
        
        # 检查上传目录结构
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
                for file in pdf_upload_files:
                    file_path = os.path.join(pdf_upload_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        logger.info(f"  上传文件: {file}, 大小: {file_size} 字节")
            
            # 列出PDF输出目录中的文件
            if os.path.exists(pdf_output_dir):
                pdf_output_files = os.listdir(pdf_output_dir)
                logger.info(f"PDF输出目录中的文件: {pdf_output_files}")
                
                # 显示每个文件的详细信息
                for file in pdf_output_files:
                    file_path = os.path.join(pdf_output_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        mtime = os.path.getmtime(file_path)
                        mod_time = datetime.fromtimestamp(mtime)
                        logger.info(f"  输出文件: {file}, 大小: {file_size} 字节, 修改时间: {mod_time}")
            else:
                logger.error("PDF输出目录不存在")
                # 尝试创建目录
                try:
                    os.makedirs(pdf_output_dir, exist_ok=True)
                    logger.info(f"已创建PDF输出目录: {pdf_output_dir}")
                except Exception as e:
                    logger.error(f"创建目录失败: {e}")
        
        # 检查配置文件
        env_file = os.path.join(project_root, '.env')
        if os.path.exists(env_file):
            logger.info(f".env文件存在: {env_file}")
            # 检查MinerU API密钥
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'MINERU_API_KEY' in content:
                        logger.info("MINERU_API_KEY在.env文件中配置")
                    else:
                        logger.warning("MINERU_API_KEY未在.env文件中配置")
            except UnicodeDecodeError:
                # 尝试使用其他编码
                try:
                    with open(env_file, 'r', encoding='gbk') as f:
                        content = f.read()
                        if 'MINERU_API_KEY' in content:
                            logger.info("MINERU_API_KEY在.env文件中配置")
                        else:
                            logger.warning("MINERU_API_KEY未在.env文件中配置")
                except Exception as e:
                    logger.error(f"使用gbk编码读取.env文件时出错: {e}")
            except Exception as e:
                logger.error(f"读取.env文件时出错: {e}")
        else:
            logger.error(f".env文件不存在: {env_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"调试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主函数"""
    logger.info("开始调试PDF翻译和下载流程")
    
    try:
        success = debug_pdf_workflow()
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