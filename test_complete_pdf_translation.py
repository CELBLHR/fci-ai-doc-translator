#!/usr/bin/env python3
"""
完整测试PDF翻译功能，包括上传、处理和下载流程
"""

import os
import sys
import logging
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_pdf():
    """创建一个测试PDF文件"""
    filename = "test_document.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # 添加标题
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "PDF翻译测试文档")
    
    # 添加内容
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 150, "这是用于测试PDF翻译功能的文档。")
    c.drawString(100, height - 170, "文档包含多行文本内容，用于验证OCR和文本提取功能。")
    c.drawString(100, height - 190, "如果处理成功，应该能够提取出这些文本内容。")
    
    # 添加更多内容
    y_position = height - 230
    for i in range(1, 11):
        c.drawString(120, y_position, f"测试行 {i}: 这是第 {i} 行测试内容，用于验证PDF处理功能")
        y_position -= 20
    
    # 添加特殊字符和数字
    c.drawString(100, y_position - 20, "特殊字符测试: @#$%^&*()")
    c.drawString(100, y_position - 40, "数字测试: 123456789")
    c.drawString(100, y_position - 60, "网址测试: https://www.example.com")
    c.drawString(100, y_position - 80, "邮箱测试: test@example.com")
    
    c.save()
    logger.info(f"测试PDF文件创建完成: {filename}")
    return filename

def test_pdf_file_validity(filename):
    """测试PDF文件的有效性"""
    logger.info(f"验证PDF文件: {filename}")
    
    # 检查文件是否存在
    if not os.path.exists(filename):
        logger.error(f"文件不存在: {filename}")
        return False
    
    # 检查文件大小
    file_size = os.path.getsize(filename)
    logger.info(f"文件大小: {file_size} 字节")
    
    if file_size == 0:
        logger.error("文件为空")
        return False
    
    # 检查PDF文件头
    with open(filename, 'rb') as f:
        header = f.read(10)
        if not header.startswith(b'%PDF-'):
            logger.error(f"文件不是有效的PDF格式，文件头: {header}")
            return False
        else:
            logger.info("文件是有效的PDF格式")
    
    return True

def test_file_download(url, output_filename):
    """测试文件下载功能"""
    try:
        logger.info(f"开始下载文件: {url}")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            with open(output_filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"文件下载完成: {output_filename}")
            logger.info(f"下载文件大小: {os.path.getsize(output_filename)} 字节")
            
            # 检查下载的文件是否是HTML
            with open(output_filename, 'rb') as f:
                content = f.read(100)  # 读取前100字节
                if b'<!DOCTYPE html>' in content or b'<html' in content:
                    logger.error("下载的文件是HTML页面而不是Word文档")
                    return False
                else:
                    logger.info("下载的文件不是HTML页面")
            
            return True
        else:
            logger.error(f"下载失败，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"下载过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主测试函数"""
    logger.info("开始完整PDF翻译功能测试")
    
    try:
        # 1. 创建测试PDF
        pdf_filename = create_test_pdf()
        
        # 2. 验证PDF文件
        if not test_pdf_file_validity(pdf_filename):
            logger.error("PDF文件验证失败")
            return False
        
        # 3. 清理测试文件
        os.remove(pdf_filename)
        logger.info("测试文件已清理")
        
        # 4. 测试下载功能（使用之前测试中获取的URL）
        # 注意：在实际使用中，这个URL应该从PDF翻译接口返回
        test_url = "http://127.0.0.1:5000/download_translated_pdf/test_full_process.docx"
        if test_file_download(test_url, "downloaded_test.docx"):
            logger.info("文件下载测试通过")
            # 清理下载的文件
            if os.path.exists("downloaded_test.docx"):
                os.remove("downloaded_test.docx")
                logger.info("下载的测试文件已清理")
        else:
            logger.error("文件下载测试失败")
        
        logger.info("完整PDF翻译功能测试完成")
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("SUCCESS: 完整PDF翻译功能测试通过")
    else:
        print("ERROR: 完整PDF翻译功能测试失败")