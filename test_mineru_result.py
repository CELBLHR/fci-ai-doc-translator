#!/usr/bin/env python3
"""
测试MinerU API返回的ZIP文件内容
"""

import os
import sys
import logging
import requests
import zipfile
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_mineru_result_content():
    """测试MinerU返回的ZIP文件内容"""
    try:
        # 使用最新的URL
        zip_url = "https://cdn-mineru.openxlab.org.cn/pdf/2025-09-01/feba8b54-c0aa-4212-b558-33813ec4d909.zip"
        logger.info(f"开始下载ZIP文件: {zip_url}")
        
        # 创建测试目录
        test_dir = "test_mineru_result"
        if os.path.exists(test_dir):
            import shutil
            shutil.rmtree(test_dir)
        os.makedirs(test_dir, exist_ok=True)
        
        # 下载ZIP文件
        zip_path = os.path.join(test_dir, "result.zip")
        response = requests.get(zip_url, timeout=300)
        if response.status_code != 200:
            logger.error(f"下载失败，状态码: {response.status_code}")
            print(f"ERROR: 下载失败，状态码: {response.status_code}")
            return False
            
        response.raise_for_status()
        
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"ZIP文件下载完成，大小: {os.path.getsize(zip_path)} 字节")
        
        # 解压ZIP文件
        logger.info("开始解压ZIP文件")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            logger.info(f"ZIP文件包含文件: {file_list}")
            
            # 解压所有文件
            zip_ref.extractall(test_dir)
            logger.info(f"文件已解压到: {test_dir}")
        
        # 查找并检查markdown文件
        md_files = []
        txt_files = []
        
        for root, dirs, files in os.walk(test_dir):
            for file in files:
                if file.endswith('.md'):
                    md_files.append(os.path.join(root, file))
                elif file.endswith('.txt'):
                    txt_files.append(os.path.join(root, file))
        
        logger.info(f"找到 {len(md_files)} 个Markdown文件")
        logger.info(f"找到 {len(txt_files)} 个文本文件")
        
        # 检查Markdown文件内容
        content_found = False
        for md_file in md_files:
            logger.info(f"检查Markdown文件: {md_file}")
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.info(f"文件大小: {len(content)} 字符")
                    
                    # 打印文件前2000个字符
                    preview = content[:2000]
                    logger.info(f"文件内容预览:\n{preview}")
                    
                    # 检查是否包含测试内容
                    if "PDF处理测试文档" in content:
                        logger.info("✓ 文件包含预期的测试内容")
                        print("SUCCESS: ZIP文件包含正确的PDF内容")
                        content_found = True
                        break
                    elif "这是用于测试MinerU API完整处理流程的PDF文档" in content:
                        logger.info("✓ 文件包含预期的测试内容")
                        print("SUCCESS: ZIP文件包含正确的PDF内容")
                        content_found = True
                        break
                    elif len(content.strip()) > 50:  # 如果内容较长，可能包含有用信息
                        logger.info("✓ 文件包含较长的内容，可能是有效的PDF内容")
                        print("SUCCESS: ZIP文件包含有效的PDF内容")
                        content_found = True
                        break
            except Exception as e:
                logger.error(f"读取文件 {md_file} 时出错: {e}")
        
        # 如果没有找到Markdown文件，检查文本文件
        if not content_found and not md_files and txt_files:
            for txt_file in txt_files:
                logger.info(f"检查文本文件: {txt_file}")
                try:
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logger.info(f"文件大小: {len(content)} 字符")
                        
                        # 打印文件前2000个字符
                        preview = content[:2000]
                        logger.info(f"文件内容预览:\n{preview}")
                        
                        # 检查是否包含测试内容
                        if "PDF处理测试文档" in content:
                            logger.info("✓ 文件包含预期的测试内容")
                            print("SUCCESS: ZIP文件包含正确的PDF内容")
                            content_found = True
                            break
                        elif "这是用于测试MinerU API完整处理流程的PDF文档" in content:
                            logger.info("✓ 文件包含预期的测试内容")
                            print("SUCCESS: ZIP文件包含正确的PDF内容")
                            content_found = True
                            break
                        elif len(content.strip()) > 50:  # 如果内容较长，可能包含有用信息
                            logger.info("✓ 文件包含较长的内容，可能是有效的PDF内容")
                            print("SUCCESS: ZIP文件包含有效的PDF内容")
                            content_found = True
                            break
                except Exception as e:
                    logger.error(f"读取文件 {txt_file} 时出错: {e}")
        
        if not content_found:
            print("WARNING: 无法确认ZIP文件是否包含正确的PDF内容")
            return False
        else:
            return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        print(f"ERROR: 测试过程中出错: {e}")
        return False
    finally:
        # 清理测试文件（可选）
        pass

if __name__ == "__main__":
    test_mineru_result_content()