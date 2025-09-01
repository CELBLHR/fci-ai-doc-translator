#!/usr/bin/env python3
"""
PDF翻译功能测试脚本
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 修复导入路径问题
sys.path.append(str(project_root / "app" / "function"))

from app.function.image_ocr.ocr_api import MinerUAPI

def create_test_pdf():
    """创建一个简单的测试PDF文件"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        # 创建临时PDF文件
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, "test_document.pdf")
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
        
        # 添加标题
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 100, "Test PDF Document")
        
        # 添加内容
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 150, "This is a test PDF document for translation.")
        c.drawString(100, height - 170, "It contains some sample text that will be processed.")
        c.drawString(100, height - 190, "The document will be converted to markdown and then to Word format.")
        
        # 添加第二页
        c.showPage()
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, height - 100, "Second Page")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 150, "This is the second page of the document.")
        c.drawString(100, height - 170, "It also contains text that will be translated.")
        
        c.save()
        
        print(f"测试PDF已创建: {pdf_path}")
        return pdf_path
    except ImportError:
        print("未安装reportlab库，无法创建测试PDF")
        print("请运行: pip install reportlab")
        return None
    except Exception as e:
        print(f"创建测试PDF时出错: {e}")
        return None

def test_mineru_api(pdf_path):
    """测试MinerU API功能"""
    try:
        # 初始化MinerU API
        mineru_api = MinerUAPI()
        print("MinerU API初始化成功")
        
        # 处理PDF
        print("开始处理PDF文件...")
        result = mineru_api.process_pdf(pdf_path)
        
        if result:
            print("PDF处理成功")
            print(f"任务ID: {result['data']['task_id']}")
            print(f"状态: {result['data']['state']}")
            return True
        else:
            print("PDF处理失败")
            return False
            
    except ValueError as e:
        print(f"MinerU API配置错误: {e}")
        print("请确保在.env文件中设置了MINERU_API_KEY")
        return False
    except Exception as e:
        print(f"测试MinerU API时出错: {e}")
        return False

def main():
    """主函数"""
    print("PDF翻译功能测试")
    print("=" * 50)
    
    # 创建测试PDF
    pdf_path = create_test_pdf()
    if not pdf_path:
        print("无法创建测试PDF，测试终止")
        return
    
    # 测试MinerU API
    success = test_mineru_api(pdf_path)
    
    # 清理测试文件
    try:
        os.remove(pdf_path)
        os.rmdir(os.path.dirname(pdf_path))
    except:
        pass
    
    if success:
        print("\n测试完成: PDF翻译功能基础组件工作正常")
    else:
        print("\n测试完成: PDF翻译功能需要进一步配置")

if __name__ == "__main__":
    main()