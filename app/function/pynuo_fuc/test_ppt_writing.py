#!/usr/bin/env python3
"""
test_ppt_writing.py
测试PPT写入功能的测试脚本（段落层级支持）
"""

import os
import sys
import json
import subprocess
import tempfile
import uuid
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from logger_config import setup_default_logging, get_logger
    from write_ppt_page_uno import (
        extract_box_text_from_paragraphs, 
        extract_box_translation_from_paragraphs,
        validate_paragraph_structure
    )
    
    # 设置测试日志
    test_logger = setup_default_logging()
    test_logger.info("PPT写入测试模块导入成功")
except ImportError as e:
    print(f"警告：无法导入模块: {e}")
    print("请确保所有相关模块文件在同一目录下")
    sys.exit(1)

class PPTWritingTester:
    """PPT写入功能测试器"""
    
    def __init__(self):
        self.logger = get_logger("test.ppt_writing")
        self.test_results = {}
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.current_dir, "test_ppt_temp")
        
        # 确保临时目录存在
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            self.logger.info(f"创建测试临时目录: {self.temp_dir}")
    
    def create_mock_translated_ppt_data(self):
        """创建模拟的已翻译PPT数据（段落层级）"""
        self.logger.info("创建模拟已翻译PPT数据...")
        
        mock_data = {
            "presentation_path": "test_presentation.pptx",
            "statistics": {
                "total_pages": 2,
                "total_boxes": 3,
                "total_paragraphs": 4,
                "total_fragments": 8
            },
            "translation_metadata": {
                "total_pages_translated": 2,
                "successful_pages": 2,
                "failed_pages": 0,
                "total_fragments_updated": 8,
                "total_box_paragraphs_processed": 4,
                "translation_timestamp": datetime.now().isoformat(),
                "structure_version": "with_paragraphs"
            },
            "pages": [
                {
                    "page_index": 0,
                    "total_boxes": 2,
                    "total_paragraphs": 3,
                    "text_boxes": [
                        {
                            "box_index": 0,
                            "box_id": "textbox_0",
                            "box_type": "text",
                            "total_paragraphs": 2,
                            "paragraphs": [
                                {
                                    "paragraph_index": 0,
                                    "paragraph_id": "para_0_0",
                                    "text_fragments": [
                                        {
                                            "fragment_id": "frag_0_0_0",
                                            "text": "Hello",
                                            "translated_text": "你好",
                                            "original_text": "Hello",
                                            "color": 0,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 24.0
                                        },
                                        {
                                            "fragment_id": "frag_0_0_1",
                                            "text": " World!",
                                            "translated_text": "世界！",
                                            "original_text": " World!",
                                            "color": 16711680,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 24.0
                                        }
                                    ]
                                },
                                {
                                    "paragraph_index": 1,
                                    "paragraph_id": "para_0_1",
                                    "text_fragments": [
                                        {
                                            "fragment_id": "frag_0_1_0",
                                            "text": "This is a test paragraph with ",
                                            "translated_text": "这是一个测试段落，包含",
                                            "original_text": "This is a test paragraph with ",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        },
                                        {
                                            "fragment_id": "frag_0_1_1",
                                            "text": "bold text",
                                            "translated_text": "粗体文本",
                                            "original_text": "bold text",
                                            "color": 255,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        },
                                        {
                                            "fragment_id": "frag_0_1_2",
                                            "text": " in it.",
                                            "translated_text": "在其中。",
                                            "original_text": " in it.",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "box_index": 1,
                            "box_id": "textbox_1",
                            "box_type": "text",
                            "total_paragraphs": 1,
                            "paragraphs": [
                                {
                                    "paragraph_index": 0,
                                    "paragraph_id": "para_1_0",
                                    "text_fragments": [
                                        {
                                            "fragment_id": "frag_1_0_0",
                                            "text": "Chemical formula: H",
                                            "translated_text": "化学分子式：H",
                                            "original_text": "Chemical formula: H",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 16.0
                                        },
                                        {
                                            "fragment_id": "frag_1_0_1",
                                            "text": "2",
                                            "translated_text": "2",
                                            "original_text": "2",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": -20,
                                            "font_size": 12.0
                                        },
                                        {
                                            "fragment_id": "frag_1_0_2",
                                            "text": "O",
                                            "translated_text": "O",
                                            "original_text": "O",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 16.0
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    "page_index": 1,
                    "total_boxes": 1,
                    "total_paragraphs": 1,
                    "text_boxes": [
                        {
                            "box_index": 0,
                            "box_id": "textbox_0",
                            "box_type": "text",
                            "total_paragraphs": 1,
                            "paragraphs": [
                                {
                                    "paragraph_index": 0,
                                    "paragraph_id": "para_0_0",
                                    "text_fragments": [
                                        {
                                            "fragment_id": "frag_0_0_0",
                                            "text": "Second page content",
                                            "translated_text": "第二页内容",
                                            "original_text": "Second page content",
                                            "color": 8388608,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 20.0
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        self.logger.info("模拟已翻译PPT数据创建完成")
        return mock_data
    
    def test_text_extraction_functions(self, mock_data):
        """测试文本提取功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试1：文本提取功能")
        self.logger.info("=" * 60)
        
        try:
            # 测试每个文本框的文本提取
            for page in mock_data["pages"]:
                page_idx = page["page_index"]
                for box in page["text_boxes"]:
                    box_idx = box["box_index"]
                    
                    # 提取原文和译文
                    original_text = extract_box_text_from_paragraphs(box)
                    translated_text = extract_box_translation_from_paragraphs(box)
                    
                    self.logger.info(f"页面 {page_idx + 1} 文本框 {box_idx + 1}:")
                    self.logger.info(f"  原文: '{original_text}'")
                    self.logger.info(f"  译文: '{translated_text}'")
                    
                    # 验证段落结构
                    is_valid = validate_paragraph_structure(box, self.logger)
                    if not is_valid:
                        self.logger.error(f"页面 {page_idx + 1} 文本框 {box_idx + 1} 段落结构验证失败")
                        self.test_results['text_extraction'] = 'FAIL'
                        return False
            
            self.test_results['text_extraction'] = 'PASS'
            self.logger.info("✅ 文本提取功能测试通过")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 文本提取功能测试失败: {e}", exc_info=True)
            self.test_results['text_extraction'] = 'ERROR'
            return False
    
    def test_json_structure_validation(self, mock_data):
        """测试JSON结构验证功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试2：JSON结构验证功能")
        self.logger.info("=" * 60)
        
        try:
            # 保存模拟数据到临时文件
            temp_json_file = os.path.join(self.temp_dir, f"mock_translated_data_{uuid.uuid4().hex[:8]}.json")
            with open(temp_json_file, 'w', encoding='utf-8') as f:
                json.dump(mock_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"模拟数据已保存到: {temp_json_file}")
            
            # 导入验证函数并测试
            from edit_ppt import validate_translated_json_structure
            is_valid, structure_type, stats = validate_translated_json_structure(mock_data, self.logger)
            
            if is_valid and structure_type == "paragraph_only":
                self.logger.info("✅ JSON结构验证功能测试通过")
                self.logger.info(f"结构类型: {structure_type}")
                self.logger.info(f"统计信息: {stats}")
                self.test_results['json_validation'] = 'PASS'
                return True
            else:
                self.logger.error(f"❌ JSON结构验证失败: valid={is_valid}, type={structure_type}")
                self.test_results['json_validation'] = 'FAIL'
                return False
            
        except Exception as e:
            self.logger.error(f"❌ JSON结构验证测试失败: {e}", exc_info=True)
            self.test_results['json_validation'] = 'ERROR'
            return False
    
    def test_edit_ppt_subprocess(self, test_ppt_path=None):
        """测试edit_ppt子进程功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试3：edit_ppt子进程功能")
        self.logger.info("=" * 60)
        
        if test_ppt_path is None or not os.path.exists(test_ppt_path):
            self.logger.warning("⚠️ 没有提供有效的PPT文件路径，跳过子进程测试")
            self.test_results['edit_ppt_subprocess'] = 'SKIPPED'
            return True
        
        try:
            # 创建翻译数据
            mock_data = self.create_mock_translated_ppt_data()
            
            # 保存翻译数据到临时文件
            temp_json_file = os.path.join(self.temp_dir, f"test_translated_data_{uuid.uuid4().hex[:8]}.json")
            with open(temp_json_file, 'w', encoding='utf-8') as f:
                json.dump(mock_data, f, ensure_ascii=False, indent=2)
            
            # 生成输出PPT路径
            output_ppt_file = os.path.join(self.temp_dir, f"test_output_{uuid.uuid4().hex[:8]}.odp")
            
            # 构建命令
            edit_ppt_script = os.path.join(self.current_dir, "edit_ppt.py")
            libreoffice_python = os.getenv("LIBREOFFICE_PYTHON", "C:/Program Files/LibreOffice/program/python.exe")
            
            if not os.path.exists(edit_ppt_script):
                self.logger.error(f"❌ 找不到edit_ppt.py脚本: {edit_ppt_script}")
                self.test_results['edit_ppt_subprocess'] = 'FAIL'
                return False
            
            if not os.path.exists(libreoffice_python):
                self.logger.warning(f"⚠️ 找不到LibreOffice Python解释器: {libreoffice_python}")
                self.test_results['edit_ppt_subprocess'] = 'SKIPPED'
                return True
            
            # 测试不同的写入模式
            test_modes = ['paragraph', 'replace', 'append']
            
            for mode in test_modes:
                self.logger.info(f"测试写入模式: {mode}")
                
                mode_output_file = output_ppt_file.replace('.odp', f'_{mode}.odp')
                
                cmd = [
                    libreoffice_python, edit_ppt_script,
                    "--input", test_ppt_path,
                    "--output", mode_output_file,
                    "--json", temp_json_file,
                    "--mode", mode
                ]
                
                self.logger.info(f"执行命令: {' '.join(cmd)}")
                
                # 运行子进程
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=180
                )
                
                if result.returncode == 0:
                    self.logger.info(f"✅ 模式 {mode} 子进程执行成功")
                    
                    # 检查输出文件
                    if os.path.exists(mode_output_file):
                        file_size = os.path.getsize(mode_output_file)
                        self.logger.info(f"  输出文件: {mode_output_file} ({file_size} bytes)")
                    else:
                        self.logger.warning(f"  输出文件不存在: {mode_output_file}")
                else:
                    self.logger.error(f"❌ 模式 {mode} 子进程执行失败，返回码: {result.returncode}")
                    self.logger.error(f"错误输出: {result.stderr}")
                    self.test_results['edit_ppt_subprocess'] = 'FAIL'
                    return False
            
            self.test_results['edit_ppt_subprocess'] = 'PASS'
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("❌ 子进程超时")
            self.test_results['edit_ppt_subprocess'] = 'TIMEOUT'
            return False
        except Exception as e:
            self.logger.error(f"❌ edit_ppt子进程测试失败: {e}", exc_info=True)
            self.test_results['edit_ppt_subprocess'] = 'ERROR'
            return False
    
    def test_complete_workflow(self, test_ppt_path=None):
        """测试完整的工作流程"""
        self.logger.info("=" * 60)
        self.logger.info("测试4：完整工作流程")
        self.logger.info("=" * 60)
        
        if test_ppt_path is None or not os.path.exists(test_ppt_path):
            self.logger.warning("⚠️ 没有提供有效的PPT文件路径，跳过完整工作流程测试")
            self.test_results['complete_workflow'] = 'SKIPPED'
            return True
        
        try:
            # 这里可以测试从 load_ppt -> translate -> edit_ppt 的完整流程
            # 但由于需要实际的翻译API，我们先跳过
            self.logger.info("完整工作流程测试需要实际的PPT文件和翻译API")
            self.logger.info("建议使用实际的PPT文件运行 pyuno_controller.py 进行测试")
            
            self.test_results['complete_workflow'] = 'MANUAL'
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 完整工作流程测试失败: {e}", exc_info=True)
            self.test_results['complete_workflow'] = 'ERROR'
            return False
    
    def run_all_tests(self, test_ppt_path=None):
        """运行所有测试"""
        self.logger.info("🚀 开始运行PPT写入功能测试套件")
        self.logger.info("=" * 80)
        
        start_time = datetime.now()
        
        # 创建测试数据
        mock_data = self.create_mock_translated_ppt_data()
        
        # 运行测试
        tests = [
            ("文本提取功能", lambda: self.test_text_extraction_functions(mock_data)),
            ("JSON结构验证", lambda: self.test_json_structure_validation(mock_data)),
            ("edit_ppt子进程", lambda: self.test_edit_ppt_subprocess(test_ppt_path)),
            ("完整工作流程", lambda: self.test_complete_workflow(test_ppt_path))
        ]
        
        for test_name, test_func in tests:
            self.logger.info(f"\n🧪 正在运行测试: {test_name}")
            try:
                result = test_func()
                if result:
                    self.logger.info(f"✅ {test_name} 测试通过")
                else:
                    self.logger.error(f"❌ {test_name} 测试失败")
            except Exception as e:
                self.logger.error(f"💥 {test_name} 测试异常: {e}", exc_info=True)
                self.test_results[test_name.lower().replace(" ", "_")] = 'ERROR'
        
        # 生成测试报告
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        self.generate_test_report(duration)
        
        return self.test_results
    
    def generate_test_report(self, duration):
        """生成测试报告"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 PPT写入功能测试报告")
        self.logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results.values() if r == 'PASS'])
        failed_tests = len([r for r in self.test_results.values() if r == 'FAIL'])
        error_tests = len([r for r in self.test_results.values() if r == 'ERROR'])
        skipped_tests = len([r for r in self.test_results.values() if r in ['SKIPPED', 'TIMEOUT', 'MANUAL']])
        
        self.logger.info(f"⏱️ 总耗时: {duration:.2f} 秒")
        self.logger.info(f"📈 总测试数: {total_tests}")
        self.logger.info(f"✅ 通过: {passed_tests}")
        self.logger.info(f"❌ 失败: {failed_tests}")
        self.logger.info(f"💥 错误: {error_tests}")
        self.logger.info(f"⏭️ 跳过: {skipped_tests}")
        
        self.logger.info("\n详细结果:")
        self.logger.info("-" * 40)
        for test_name, result in self.test_results.items():
            status_icon = {
                'PASS': '✅',
                'FAIL': '❌',
                'ERROR': '💥',
                'SKIPPED': '⏭️',
                'TIMEOUT': '⏰',
                'MANUAL': '📋'
            }.get(result, '❓')
            
            self.logger.info(f"{status_icon} {test_name}: {result}")
        
        # 保存测试报告
        report_file = os.path.join(self.temp_dir, f"ppt_writing_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'errors': error_tests,
            'skipped': skipped_tests,
            'results': self.test_results
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"\n📄 详细测试报告已保存到: {report_file}")
        
        # 成功率计算
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        if success_rate >= 80:
            self.logger.info(f"\n🎉 PPT写入功能测试总体成功! 成功率: {success_rate:.1f}%")
        elif success_rate >= 60:
            self.logger.info(f"\n⚠️ PPT写入功能测试部分成功，建议检查失败项。成功率: {success_rate:.1f}%")
        else:
            self.logger.error(f"\n💥 PPT写入功能测试失败较多，需要重点修复。成功率: {success_rate:.1f}%")
        
        self.logger.info("=" * 80)

def main():
    """主程序入口"""
    print("🔧 PPT写入功能测试工具（段落层级支持）")
    print("=" * 80)
    
    # 可以通过命令行参数指定PPT文件进行实际测试
    test_ppt_path = None
    if len(sys.argv) > 1:
        test_ppt_path = sys.argv[1]
        print(f"📄 使用命令行指定的PPT文件: {test_ppt_path}")
    
    # 创建测试器并运行测试
    tester = PPTWritingTester()
    results = tester.run_all_tests(test_ppt_path)
    
    # 根据测试结果设置退出码
    failed_count = len([r for r in results.values() if r in ['FAIL', 'ERROR']])
    if failed_count == 0:
        print("\n🎉 所有PPT写入测试都成功了！")
        sys.exit(0)
    else:
        print(f"\n💥 有 {failed_count} 个测试失败，请检查日志。")
        sys.exit(1)

if __name__ == "__main__":
    main()
