#!/usr/bin/env python3
"""
test_paragraph_structure.py
测试新的段落层级结构的PPT加载功能
"""
import subprocess
import json
import os
import tempfile
import sys
from datetime import datetime
import uuid

def test_load_ppt_with_paragraphs(ppt_path, test_name="段落结构测试"):
    """
    测试新的load_ppt子进程功能（包含段落层级）
    
    Args:
        ppt_path: PPT文件路径
        test_name: 测试名称
    
    Returns:
        bool: 测试是否成功
    """
    print("=" * 80)
    print(f"开始测试: {test_name}")
    print(f"PPT文件: {ppt_path}")
    print("=" * 80)
    
    # 检查PPT文件是否存在
    if not os.path.exists(ppt_path):
        print(f"❌ 错误：PPT文件不存在: {ppt_path}")
        return False
    
    # 获取当前脚本目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建temp目录
    temp_dir = os.path.join(current_dir, "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        print(f"✅ 创建temp目录: {temp_dir}")
    
    # 生成唯一的输出文件名
    output_filename = f"test_paragraph_result_{uuid.uuid4().hex[:8]}.json"
    output_file = os.path.join(temp_dir, output_filename)
    
    # 构建load_ppt.py脚本路径
    load_ppt_script = os.path.join(current_dir, "load_ppt.py")
    
    if not os.path.exists(load_ppt_script):
        print(f"❌ 错误：找不到load_ppt.py脚本: {load_ppt_script}")
        return False
    
    # LibreOffice Python解释器路径
    libreoffice_python = "C:/Program Files/LibreOffice/program/python.exe"
    
    if not os.path.exists(libreoffice_python):
        print(f"❌ 错误：找不到LibreOffice Python解释器: {libreoffice_python}")
        print("请确认LibreOffice已正确安装")
        return False
    
    # 构建命令
    cmd = [
        libreoffice_python, load_ppt_script,
        "--input", ppt_path,
        "--output", output_file
    ]
    
    print(f"🚀 启动子进程命令: {' '.join(cmd)}")
    print(f"📁 工作目录: {current_dir}")
    print(f"📄 输出文件: {output_file}")
    print("-" * 60)
    
    try:
        # 运行子进程
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        print("⏳ 正在执行子进程...")
        start_time = datetime.now()
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=current_dir,
            env=env,
            timeout=180
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"⏱️  子进程执行时间: {duration:.2f} 秒")
        print(f"🔢 返回码: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ 子进程执行成功")
            
            # 显示子进程输出（如果有）
            if result.stdout.strip():
                print("\n📋 子进程标准输出:")
                print("-" * 40)
                print(result.stdout)
                print("-" * 40)
            
            # 检查输出文件是否存在
            if os.path.exists(output_file):
                print(f"✅ 找到输出文件: {output_file}")
                
                # 读取并验证JSON结果
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    print("✅ JSON文件解析成功")
                    
                    # 验证新的段落结构
                    success = validate_paragraph_structure(data)
                    
                    if success:
                        print("\n🎉 测试完全成功！")
                        
                        # 显示详细统计信息
                        display_detailed_statistics(data)
                        
                        # 可选：保存测试结果副本
                        save_test_result_copy(data, test_name)
                        
                        return True
                    else:
                        print("\n❌ 段落结构验证失败")
                        return False
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析失败: {e}")
                    return False
                except Exception as e:
                    print(f"❌ 读取输出文件失败: {e}")
                    return False
            else:
                print(f"❌ 未找到输出文件: {output_file}")
                return False
        else:
            print(f"❌ 子进程执行失败，返回码: {result.returncode}")
            if result.stderr.strip():
                print("\n📋 子进程错误输出:")
                print("-" * 40)
                print(result.stderr)
                print("-" * 40)
            if result.stdout.strip():
                print("\n📋 子进程标准输出:")
                print("-" * 40)
                print(result.stdout)
                print("-" * 40)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 子进程超时（180秒）")
        print("\n💡 可能的原因：")
        print("1. LibreOffice监听服务未启动")
        print("2. PPT文件过大或复杂") 
        print("3. 系统资源不足")
        print("\n🔧 请确保LibreOffice服务正在运行：")
        print("soffice --headless --accept=\"socket,host=localhost,port=2002;urp;StarOffice.ComponentContext\"")
        return False
    except Exception as e:
        print(f"❌ 运行子进程时出错: {str(e)}")
        return False
    finally:
        # 清理临时文件（测试完成后可选择保留）
        try:
            if os.path.exists(output_file):
                # 暂时不删除，以便调试
                print(f"📄 临时文件保留: {output_file}")
                # os.remove(output_file)
                # print(f"🗑️  已删除临时文件: {output_file}")
        except Exception as e:
            print(f"⚠️  删除临时文件失败: {str(e)}")

def validate_paragraph_structure(data):
    """
    验证JSON数据是否包含正确的段落层级结构
    
    Args:
        data: 从load_ppt返回的JSON数据
    
    Returns:
        bool: 验证是否成功
    """
    print("\n🔍 开始验证段落结构...")
    
    try:
        # 检查顶级结构
        required_top_keys = ['presentation_path', 'statistics', 'pages']
        for key in required_top_keys:
            if key not in data:
                print(f"❌ 缺少顶级字段: {key}")
                return False
        
        print("✅ 顶级结构正确")
        
        # 检查统计信息
        stats = data['statistics']
        required_stat_keys = ['total_pages', 'total_boxes', 'total_paragraphs', 'total_fragments']
        for key in required_stat_keys:
            if key not in stats:
                print(f"❌ 统计信息缺少字段: {key}")
                return False
        
        print("✅ 统计信息结构正确")
        print(f"📊 统计：{stats['total_pages']} 页，{stats['total_boxes']} 文本框，{stats['total_paragraphs']} 段落，{stats['total_fragments']} 片段")
        
        # 检查页面结构
        pages = data['pages']
        if not isinstance(pages, list):
            print("❌ pages字段不是数组")
            return False
        
        total_validated_paragraphs = 0
        total_validated_fragments = 0
        
        for page_idx, page in enumerate(pages):
            # 检查页面字段
            required_page_keys = ['page_index', 'total_boxes', 'total_paragraphs', 'text_boxes']
            for key in required_page_keys:
                if key not in page:
                    print(f"❌ 页面 {page_idx} 缺少字段: {key}")
                    return False
            
            # 检查文本框结构
            text_boxes = page['text_boxes']
            if not isinstance(text_boxes, list):
                print(f"❌ 页面 {page_idx} 的text_boxes不是数组")
                return False
            
            page_paragraphs = 0
            for box_idx, text_box in enumerate(text_boxes):
                # 检查文本框字段
                required_box_keys = ['box_index', 'box_id', 'box_type', 'total_paragraphs', 'paragraphs']
                for key in required_box_keys:
                    if key not in text_box:
                        print(f"❌ 页面 {page_idx} 文本框 {box_idx} 缺少字段: {key}")
                        return False
                
                # 检查段落结构（这是新增的层级）
                paragraphs = text_box['paragraphs']
                if not isinstance(paragraphs, list):
                    print(f"❌ 页面 {page_idx} 文本框 {box_idx} 的paragraphs不是数组")
                    return False
                
                page_paragraphs += len(paragraphs)
                
                for para_idx, paragraph in enumerate(paragraphs):
                    # 检查段落字段
                    required_para_keys = ['paragraph_index', 'paragraph_id', 'text_fragments']
                    for key in required_para_keys:
                        if key not in paragraph:
                            print(f"❌ 页面 {page_idx} 文本框 {box_idx} 段落 {para_idx} 缺少字段: {key}")
                            return False
                    
                    # 检查文本片段结构
                    text_fragments = paragraph['text_fragments']
                    if not isinstance(text_fragments, list):
                        print(f"❌ 页面 {page_idx} 文本框 {box_idx} 段落 {para_idx} 的text_fragments不是数组")
                        return False
                    
                    total_validated_fragments += len(text_fragments)
                    
                    for frag_idx, fragment in enumerate(text_fragments):
                        # 检查片段字段
                        required_frag_keys = ['fragment_id', 'text', 'color', 'underline', 'bold', 'escapement', 'font_size']
                        for key in required_frag_keys:
                            if key not in fragment:
                                print(f"❌ 页面 {page_idx} 文本框 {box_idx} 段落 {para_idx} 片段 {frag_idx} 缺少字段: {key}")
                                return False
                
                # 验证文本框的段落数量是否一致
                if text_box['total_paragraphs'] != len(paragraphs):
                    print(f"❌ 页面 {page_idx} 文本框 {box_idx} 段落数量不一致：声明 {text_box['total_paragraphs']}，实际 {len(paragraphs)}")
                    return False
            
            # 验证页面的段落数量是否一致
            if page['total_paragraphs'] != page_paragraphs:
                print(f"❌ 页面 {page_idx} 段落数量不一致：声明 {page['total_paragraphs']}，实际 {page_paragraphs}")
                return False
            
            total_validated_paragraphs += page_paragraphs
        
        # 验证总体统计数量是否一致
        if stats['total_paragraphs'] != total_validated_paragraphs:
            print(f"❌ 总段落数量不一致：声明 {stats['total_paragraphs']}，实际 {total_validated_paragraphs}")
            return False
        
        if stats['total_fragments'] != total_validated_fragments:
            print(f"❌ 总片段数量不一致：声明 {stats['total_fragments']}，实际 {total_validated_fragments}")
            return False
        
        print("✅ 段落层级结构验证完全成功")
        print(f"✅ 验证的段落数量: {total_validated_paragraphs}")
        print(f"✅ 验证的片段数量: {total_validated_fragments}")
        
        return True
        
    except Exception as e:
        print(f"❌ 验证过程中出错: {str(e)}")
        return False

def display_detailed_statistics(data):
    """
    显示详细的统计信息
    """
    print("\n" + "=" * 60)
    print("📊 详细统计信息")
    print("=" * 60)
    
    stats = data['statistics']
    pages = data['pages']
    
    print(f"📄 总页数: {stats['total_pages']}")
    print(f"📦 总文本框数: {stats['total_boxes']}")
    print(f"📝 总段落数: {stats['total_paragraphs']}")
    print(f"🔤 总文本片段数: {stats['total_fragments']}")
    print("-" * 60)
    
    # 按页面显示详细信息
    for page in pages:
        print(f"页面 {page['page_index'] + 1}:")
        print(f"  📦 文本框: {page['total_boxes']}")
        print(f"  📝 段落: {page['total_paragraphs']}")
        
        # 显示每个文本框的段落分布
        for text_box in page['text_boxes']:
            print(f"    文本框 {text_box['box_index']} ({text_box['box_id']}):")
            print(f"      📝 段落数: {text_box['total_paragraphs']}")
            
            # 显示每个段落的内容预览
            for paragraph in text_box['paragraphs']:
                paragraph_text = "".join([frag['text'] for frag in paragraph['text_fragments']])
                preview = paragraph_text.strip()
                if len(preview) > 50:
                    preview = preview[:50] + "..."
                print(f"        段落 {paragraph['paragraph_index']}: '{preview}' ({len(paragraph['text_fragments'])} 片段)")
    
    print("=" * 60)

def save_test_result_copy(data, test_name):
    """
    保存测试结果副本以供后续分析
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(current_dir, "test_results")
        
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(results_dir, f"paragraph_test_{timestamp}.json")
        
        test_result = {
            "test_name": test_name,
            "test_time": timestamp,
            "validation_passed": True,
            "data": data
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 测试结果已保存: {result_file}")
        
    except Exception as e:
        print(f"⚠️  保存测试结果失败: {str(e)}")

def run_multiple_tests():
    """
    运行多个测试用例
    """
    print("🚀 开始运行段落结构测试套件")
    print("=" * 80)
    
    # 测试用例列表（请根据实际情况修改PPT文件路径）
    test_cases = [
        {
            "name": "基础段落测试",
            "ppt_path": "F:/pptxTest/pyuno/test_ppt/test.pptx",  # 请修改为实际的PPT文件路径
            "description": "测试基本的段落结构识别功能"
        },
        # 可以添加更多测试用例
        # {
        #     "name": "复杂段落测试",
        #     "ppt_path": "test_complex.pptx",
        #     "description": "测试包含复杂格式的段落结构"
        # },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 测试用例 {i}/{len(test_cases)}: {test_case['name']}")
        print(f"📝 描述: {test_case['description']}")
        
        success = test_load_ppt_with_paragraphs(
            test_case['ppt_path'], 
            test_case['name']
        )
        
        results.append({
            "name": test_case['name'],
            "success": success
        })
        
        if success:
            print(f"✅ 测试用例 {i} 成功")
        else:
            print(f"❌ 测试用例 {i} 失败")
    
    # 显示总体结果
    print("\n" + "=" * 80)
    print("📋 测试总结")
    print("=" * 80)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    print(f"✅ 成功测试: {len(successful_tests)}/{len(results)}")
    print(f"❌ 失败测试: {len(failed_tests)}/{len(results)}")
    
    if failed_tests:
        print("\n❌ 失败的测试用例:")
        for test in failed_tests:
            print(f"  - {test['name']}")
    
    if len(successful_tests) == len(results):
        print("\n🎉 所有测试都成功了！段落结构功能正常工作！")
    else:
        print(f"\n⚠️  有 {len(failed_tests)} 个测试失败，请检查相关问题")

def main():
    """
    主程序入口
    """
    print("🔧 段落结构测试工具")
    print("=" * 80)
    
    # 可以通过命令行参数指定单个PPT文件进行测试
    if len(sys.argv) > 1:
        ppt_path = sys.argv[1]
        print(f"📄 使用命令行指定的PPT文件: {ppt_path}")
        
        success = test_load_ppt_with_paragraphs(ppt_path, "命令行测试")
        
        if success:
            print("\n🎉 测试成功！")
            sys.exit(0)
        else:
            print("\n❌ 测试失败！")
            sys.exit(1)
    else:
        # 运行预定义的测试套件
        run_multiple_tests()

if __name__ == "__main__":
    main()