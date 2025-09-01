#!/usr/bin/env python3
"""
测试MinerU API完整PDF处理流程
"""

import os
import sys
import logging
import time
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_mineru_full_process():
    """测试MinerU完整PDF处理流程"""
    try:
        # 导入必要的模块
        from app.function.image_ocr.ocr_api import MinerUAPI
        
        # 初始化MinerU API
        logger.info("初始化MinerU API")
        mineru_api = MinerUAPI()
        logger.info("MinerU API初始化成功")
        
        # 创建一个测试PDF文件
        test_pdf_path = "test_full_process.pdf"
        logger.info(f"创建测试PDF文件: {test_pdf_path}")
        
        # 创建一个包含特定内容的PDF文件用于测试
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        c = canvas.Canvas(test_pdf_path, pagesize=letter)
        width, height = letter
        
        # 添加标题
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 100, "PDF处理测试文档")
        
        # 添加内容
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 150, "这是用于测试MinerU API完整处理流程的PDF文档。")
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
        
        logger.info("测试PDF文件创建完成")
        logger.info(f"文件大小: {os.path.getsize(test_pdf_path)} 字节")
        
        # 验证文件是否正确创建
        if not os.path.exists(test_pdf_path):
            logger.error("测试PDF文件创建失败")
            print("ERROR: 测试PDF文件创建失败")
            return False
            
        # 测试完整的PDF处理流程
        logger.info("开始测试完整PDF处理流程")
        result = mineru_api.process_pdf(test_pdf_path)
        
        if result:
            logger.info("PDF处理完成，返回结果:")
            logger.info(f"完整结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 检查结果中的关键信息
            if 'code' in result and result['code'] == 0:
                logger.info("处理结果状态码正常")
                
                if 'data' in result and 'task_id' in result['data']:
                    task_id = result['data']['task_id']
                    logger.info(f"任务ID: {task_id}")
                    
                    if 'full_zip_url' in result['data']:
                        zip_url = result['data']['full_zip_url']
                        logger.info(f"ZIP文件下载地址: {zip_url}")
                        print(f"SUCCESS: PDF处理成功完成")
                        print(f"任务ID: {task_id}")
                        print(f"下载地址: {zip_url}")
                        
                        # 将结果保存到文件以便后续分析
                        with open('mineru_result.json', 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)
                        logger.info("结果已保存到 mineru_result.json")
                        
                        return True
                    else:
                        logger.error("结果中缺少full_zip_url")
                else:
                    logger.error("结果中缺少任务ID")
            else:
                error_msg = result.get('msg', '未知错误')
                logger.error(f"处理失败: {error_msg}")
        else:
            logger.error("PDF处理失败，返回空结果")
            print("ERROR: PDF处理失败")
            return False
            
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        print(f"ERROR: 测试过程中出错: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists("test_full_process.pdf"):
            os.remove("test_full_process.pdf")
            logger.info("测试文件已清理")

if __name__ == "__main__":
    test_mineru_full_process()