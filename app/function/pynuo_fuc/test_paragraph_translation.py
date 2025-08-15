#!/usr/bin/env python3
"""
test_paragraph_translation.py
测试段落层级翻译功能的综合测试脚本
"""

import os
import sys
import json
import subprocess
from datetime import datetime
import uuid
import tempfile

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from logger_config import setup_default_logging, get_logger
    from ppt_data_utils import extract_texts_for_translation, map_translation_results_back
    from api_translate_uno import format_page_text_for_translation, separate_translate_text, validate_translation_result
    
    # 设置测试日志
    test_logger = setup_default_logging()
    test_logger.info("日志系统和模块导入成功")
except ImportError as e:
    print(f"警告：无法导入模块: {e}")
    print("请确保所有相关模块文件在同一目录下")
    sys.exit(1)

class ParagraphTranslationTester:
    """段落层级翻译功能测试器"""
    
    def __init__(self):
        self.logger = get_logger("test.paragraph_translation")
        self.test_results = {}
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.temp_dir = os.path.join(self.current_dir, "test_temp")
        
        # 确保临时目录存在
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            self.logger.info(f"创建测试临时目录: {self.temp_dir}")
    
    def create_mock_ppt_data(self):
        """创建模拟的PPT数据（包含段落层级）"""
        self.logger.info("创建模拟PPT数据...")
        
        mock_data = {
            "presentation_path": "test_presentation.pptx",
            "statistics": {
                "total_pages": 2,
                "total_boxes": 3,
                "total_paragraphs": 5,
                "total_fragments": 12
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
                                            "color": 0,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 24.0
                                        },
                                        {
                                            "fragment_id": "frag_0_0_1",
                                            "text": " World",
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
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        },
                                        {
                                            "fragment_id": "frag_0_1_1",
                                            "text": "bold text",
                                            "color": 255,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        },
                                        {
                                            "fragment_id": "frag_0_1_2",
                                            "text": " in the middle.",
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
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 16.0
                                        },
                                        {
                                            "fragment_id": "frag_1_0_1",
                                            "text": "2",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": -20,
                                            "font_size": 12.0
                                        },
                                        {
                                            "fragment_id": "frag_1_0_2",
                                            "text": "O + CO",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 16.0
                                        },
                                        {
                                            "fragment_id": "frag_1_0_3",
                                            "text": "2",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": -20,
                                            "font_size": 12.0
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
                    "total_paragraphs": 2,
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
                                            "text": "Second page title",
                                            "color": 8388608,
                                            "underline": False,
                                            "bold": True,
                                            "escapement": 0,
                                            "font_size": 20.0
                                        }
                                    ]
                                },
                                {
                                    "paragraph_index": 1,
                                    "paragraph_id": "para_0_1",
                                    "text_fragments": [
                                        {
                                            "fragment_id": "frag_0_1_0",
                                            "text": "Second page content with ",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        },
                                        {
                                            "fragment_id": "frag_0_1_1",
                                            "text": "superscript",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 30,
                                            "font_size": 10.0
                                        },
                                        {
                                            "fragment_id": "frag_0_1_2",
                                            "text": " text example.",
                                            "color": 0,
                                            "underline": False,
                                            "bold": False,
                                            "escapement": 0,
                                            "font_size": 14.0
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        self.logger.info("模拟PPT数据创建完成")
        return mock_data
    
    def create_mock_translation_result(self):
        """创建模拟的翻译结果"""
        self.logger.info("创建模拟翻译结果...")
        
        mock_translation_results = {
            0: {
                'original_content': 'Page 1 content...',
                'translated_json': '''[
                    {
                        "box_index": 1,
                        "paragraph_index": 1,
                        "source_language": "Hello[block] World",
                        "target_language": "你好[block]世界"
                    },
                    {
                        "box_index": 1,
                        "paragraph_index": 2,
                        "source_language": "This is a test paragraph with [block]bold text[block] in the middle.",
                        "target_language": "这是一个测试段落，包含[block]粗体文本[block]在中间。"
                    },
                    {
                        "box_index": 2,
                        "paragraph_index": 1,
                        "source_language": "Chemical formula: H[block]2[block]O + CO[block]2",
                        "target_language": "化学分子式：H[block]2[block]O + CO[block]2"
                    }
                ]''',
                'translated_fragments': {
                    '1_1': ['你好', '世界'],
                    '1_2': ['这是一个测试段落，包含', '粗体文本', '在中间。'],
                    '2_1': ['化学分子式：H', '2', 'O + CO', '2']
                },
                'box_paragraph_count': 3,
                'box_count': 2
            },
            1: {
                'original_content': 'Page 2 content...',
                'translated_json': '''[
                    {
                        "box_index": 1,
                        "paragraph_index": 1,
                        "source_language": "Second page title",
                        "target_language": "第二页标题"
                    },
                    {
                        "box_index": 1,
                        "paragraph_index": 2,
                        "source_language": "Second page content with [block]superscript[block] text example.",
                        "target_language": "第二页内容包含[block]上标[block]文本示例。"
                    }
                ]''',
                'translated_fragments': {
                    '1_1': ['第二页标题'],
                    '1_2': ['第二页内容包含', '上标', '文本示例。']
                },
                'box_paragraph_count': 2,
                'box_count': 1
            }
        }
        
        self.logger.info("模拟翻译结果创建完成")
        return mock_translation_results
    
    def test_text_extraction(self, mock_ppt_data):
        """测试文本提取功能（段落层级）"""
        self.logger.info("=" * 60)
        self.logger.info("测试1：文本提取功能（段落层级）")
        self.logger.info("=" * 60)
        
        try:
            text_boxes_data, fragment_mapping = extract_texts_for_translation(mock_ppt_data)
            
            # 验证提取结果
            expected_box_paragraphs = 5  # 根据mock数据
            actual_box_paragraphs = len(text_boxes_data)
            
            if actual_box_paragraphs == expected_box_paragraphs:
                self.logger.info(f"✅ 文本框段落数量正确: {actual_box_paragraphs}")
                self.test_results['text_extraction'] = 'PASS'
            else:
                self.logger.error(f"❌ 文本框段落数量错误: 期望 {expected_box_paragraphs}, 实际 {actual_box_paragraphs}")
                self.test_results['text_extraction'] = 'FAIL'
                return False
            
            # 验证数据结构
            for i, box_para in enumerate(text_boxes_data):
                required_keys = ['page_index', 'box_index', 'box_id', 'paragraph_index', 'paragraph_id', 'texts', 'combined_text']
                for key in required_keys:
                    if key not in box_para:
                        self.logger.error(f"❌ 文本框段落 {i} 缺少字段: {key}")
                        self.test_results['text_extraction'] = 'FAIL'
                        return False
                
                self.logger.info(f"文本框段落 {i+1}: {box_para['box_id']}.{box_para['paragraph_id']} - {len(box_para['texts'])} 个片段")
                self.logger.info(f"  合并文本: '{box_para['combined_text']}'")
            
            self.logger.info("✅ 文本提取测试通过")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 文本提取测试失败: {e}", exc_info=True)
            self.test_results['text_extraction'] = 'ERROR'
            return False
    
    def test_text_formatting(self, text_boxes_data):
        """测试文本格式化功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试2：文本格式化功能")
        self.logger.info("=" * 60)
        
        try:
            # 测试第一页的格式化
            page_0_content = format_page_text_for_translation(text_boxes_data, 0)
            page_1_content = format_page_text_for_translation(text_boxes_data, 1)
            
            self.logger.info("第1页格式化内容:")
            self.logger.info("-" * 40)
            self.logger.info(page_0_content)
            self.logger.info("-" * 40)
            
            self.logger.info("第2页格式化内容:")
            self.logger.info("-" * 40)
            self.logger.info(page_1_content)
            self.logger.info("-" * 40)
            
            # 验证格式化结果
            if "【文本框1-段落1】" in page_0_content and "【文本框1-段落2】" in page_0_content:
                self.logger.info("✅ 格式化内容包含正确的段落标识")
                self.test_results['text_formatting'] = 'PASS'
            else:
                self.logger.error("❌ 格式化内容缺少段落标识")
                self.test_results['text_formatting'] = 'FAIL'
                return False
            
            self.logger.info("✅ 文本格式化测试通过")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 文本格式化测试失败: {e}", exc_info=True)
            self.test_results['text_formatting'] = 'ERROR'
            return False
    
    def test_translation_result_parsing(self, mock_translation_results):
        """测试翻译结果解析功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试3：翻译结果解析功能")
        self.logger.info("=" * 60)
        
        try:
            for page_index, translation_result in mock_translation_results.items():
                translated_json = translation_result['translated_json']
                
                self.logger.info(f"解析第 {page_index + 1} 页翻译结果:")
                self.logger.info("-" * 40)
                self.logger.info(translated_json)
                self.logger.info("-" * 40)
                
                # 解析翻译结果
                translated_fragments = separate_translate_text(translated_json)
                
                self.logger.info("解析后的翻译片段:")
                for key, fragments in translated_fragments.items():
                    self.logger.info(f"  {key}: {fragments}")
                
                # 验证解析结果
                expected_fragments = translation_result['translated_fragments']
                if translated_fragments == expected_fragments:
                    self.logger.info(f"✅ 第 {page_index + 1} 页翻译结果解析正确")
                else:
                    self.logger.error(f"❌ 第 {page_index + 1} 页翻译结果解析错误")
                    self.logger.error(f"期望: {expected_fragments}")
                    self.logger.error(f"实际: {translated_fragments}")
                    self.test_results['translation_parsing'] = 'FAIL'
                    return False
            
            self.test_results['translation_parsing'] = 'PASS'
            self.logger.info("✅ 翻译结果解析测试通过")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 翻译结果解析测试失败: {e}", exc_info=True)
            self.test_results['translation_parsing'] = 'ERROR'
            return False
    
    def test_translation_mapping(self, mock_ppt_data, mock_translation_results, text_boxes_data):
        """测试翻译结果映射功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试4：翻译结果映射功能")
        self.logger.info("=" * 60)
        
        try:
            translated_ppt_data = map_translation_results_back(
                mock_ppt_data, 
                mock_translation_results, 
                text_boxes_data
            )
            
            # 验证映射结果
            updated_fragments = 0
            for page_data in translated_ppt_data['pages']:
                for text_box in page_data['text_boxes']:
                    for paragraph in text_box['paragraphs']:
                        for fragment in paragraph['text_fragments']:
                            if 'translated_text' in fragment:
                                updated_fragments += 1
                                self.logger.debug(f"更新片段: '{fragment['text']}' -> '{fragment['translated_text']}'")
            
            expected_fragments = sum(len(bp['texts']) for bp in text_boxes_data)
            
            self.logger.info(f"期望更新片段数: {expected_fragments}")
            self.logger.info(f"实际更新片段数: {updated_fragments}")
            
            if updated_fragments > 0:
                self.logger.info("✅ 翻译结果映射成功")
                self.test_results['translation_mapping'] = 'PASS'
                
                # 保存映射结果用于检查
                result_file = os.path.join(self.temp_dir, "translated_ppt_data_test.json")
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(translated_ppt_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"翻译映射结果已保存到: {result_file}")
                
                return True
            else:
                self.logger.error("❌ 没有片段被更新")
                self.test_results['translation_mapping'] = 'FAIL'
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 翻译结果映射测试失败: {e}", exc_info=True)
            self.test_results['translation_mapping'] = 'ERROR'
            return False
    
    def test_validation_function(self, mock_translation_results, text_boxes_data):
        """测试翻译结果验证功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试5：翻译结果验证功能")
        self.logger.info("=" * 60)
        
        try:
            validation_stats = validate_translation_result(mock_translation_results, text_boxes_data)
            
            self.logger.info("验证统计结果:")
            for key, value in validation_stats.items():
                self.logger.info(f"  {key}: {value}")
            
            # 检查验证结果
            if validation_stats['translation_coverage'] > 80:  # 翻译覆盖率应该大于80%
                self.logger.info(f"✅ 翻译覆盖率良好: {validation_stats['translation_coverage']:.2f}%")
                self.test_results['validation'] = 'PASS'
                return True
            else:
                self.logger.warning(f"⚠️  翻译覆盖率较低: {validation_stats['translation_coverage']:.2f}%")
                self.test_results['validation'] = 'PARTIAL'
                return True
            
        except Exception as e:
            self.logger.error(f"❌ 翻译结果验证测试失败: {e}", exc_info=True)
            self.test_results['validation'] = 'ERROR'
            return False
    
    def test_load_ppt_subprocess(self, test_ppt_path=None):
        """测试load_ppt子进程功能"""
        self.logger.info("=" * 60)
        self.logger.info("测试6：load_ppt子进程功能")
        self.logger.info("=" * 60)
        
        if test_ppt_path is None or not os.path.exists(test_ppt_path):
            self.logger.warning("⚠️  没有提供有效的PPT文件路径，跳过子进程测试")
            self.test_results['subprocess'] = 'SKIPPED'
            return True
        
        try:
            # 生成输出文件
            output_file = os.path.join(self.temp_dir, f"subprocess_test_{uuid.uuid4().hex[:8]}.json")
            
            # 构建命令
            load_ppt_script = os.path.join(self.current_dir, "load_ppt.py")
            libreoffice_python = "C:/Program Files/LibreOffice/program/python.exe"
            
            if not os.path.exists(load_ppt_script):
                self.logger.error(f"❌ 找不到load_ppt.py脚本: {load_ppt_script}")
                self.test_results['subprocess'] = 'FAIL'
                return False
            
            if not os.path.exists(libreoffice_python):
                self.logger.warning(f"⚠️  找不到LibreOffice Python解释器: {libreoffice_python}")
                self.test_results['subprocess'] = 'SKIPPED'
                return True
            
            cmd = [
                libreoffice_python, load_ppt_script,
                "--input", test_ppt_path,
                "--output", output_file
            ]
            
            self.logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 运行子进程
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=120
            )
            
            if result.returncode == 0:
                self.logger.info("✅ 子进程执行成功")
                
                # 检查输出文件
                if os.path.exists(output_file):
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    stats = data.get('statistics', {})
                    self.logger.info(f"PPT统计: {stats}")
                    
                    # 验证段落层级结构
                    pages = data.get('pages', [])
                    has_paragraphs = False
                    for page in pages:
                        for text_box in page.get('text_boxes', []):
                            if 'paragraphs' in text_box:
                                has_paragraphs = True
                                break
                        if has_paragraphs:
                            break
                    
                    if has_paragraphs:
                        self.logger.info("✅ 子进程输出包含段落层级结构")
                        self.test_results['subprocess'] = 'PASS'
                        return True
                    else:
                        self.logger.error("❌ 子进程输出缺少段落层级结构")
                        self.test_results['subprocess'] = 'FAIL'
                        return False
                else:
                    self.logger.error(f"❌ 未找到输出文件: {output_file}")
                    self.test_results['subprocess'] = 'FAIL'
                    return False
            else:
                self.logger.error(f"❌ 子进程执行失败，返回码: {result.returncode}")
                self.logger.error(f"错误输出: {result.stderr}")
                self.test_results['subprocess'] = 'FAIL'
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("❌ 子进程超时")
            self.test_results['subprocess'] = 'TIMEOUT'
            return False
        except Exception as e:
            self.logger.error(f"❌ 子进程测试失败: {e}", exc_info=True)
            self.test_results['subprocess'] = 'ERROR'
            return False
    
    def run_all_tests(self, test_ppt_path=None):
        """运行所有测试"""
        self.logger.info("🚀 开始运行段落层级翻译功能测试套件")
        self.logger.info("=" * 80)
        
        start_time = datetime.now()
        
        # 创建测试数据
        mock_ppt_data = self.create_mock_ppt_data()
        mock_translation_results = self.create_mock_translation_result()
        
        # 运行测试
        tests = [
            ("文本提取", lambda: self.test_text_extraction(mock_ppt_data)),
            ("文本格式化", lambda: self.test_text_formatting(None)),  # 会在文本提取后设置
            ("翻译结果解析", lambda: self.test_translation_result_parsing(mock_translation_results)),
            ("翻译结果映射", lambda: self.test_translation_mapping(mock_ppt_data, mock_translation_results, None)),
            ("翻译结果验证", lambda: self.test_validation_function(mock_translation_results, None)),
            ("子进程功能", lambda: self.test_load_ppt_subprocess(test_ppt_path))
        ]
        
        text_boxes_data = None
        
        for test_name, test_func in tests:
            self.logger.info(f"\n🧪 正在运行测试: {test_name}")
            try:
                if test_name == "文本提取":
                    result = test_func()
                    if result:
                        text_boxes_data, _ = extract_texts_for_translation(mock_ppt_data)
                elif test_name in ["文本格式化", "翻译结果映射", "翻译结果验证"]:
                    if text_boxes_data is not None:
                        if test_name == "文本格式化":
                            result = self.test_text_formatting(text_boxes_data)
                        elif test_name == "翻译结果映射":
                            result = self.test_translation_mapping(mock_ppt_data, mock_translation_results, text_boxes_data)
                        elif test_name == "翻译结果验证":
                            result = self.test_validation_function(mock_translation_results, text_boxes_data)
                    else:
                        self.logger.error(f"❌ {test_name} 测试依赖于文本提取结果，但文本提取失败")
                        result = False
                else:
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
        self.logger.info("📊 测试报告")
        self.logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results.values() if r == 'PASS'])
        failed_tests = len([r for r in self.test_results.values() if r == 'FAIL'])
        error_tests = len([r for r in self.test_results.values() if r == 'ERROR'])
        skipped_tests = len([r for r in self.test_results.values() if r in ['SKIPPED', 'TIMEOUT']])
        
        self.logger.info(f"⏱️  总耗时: {duration:.2f} 秒")
        self.logger.info(f"📈 总测试数: {total_tests}")
        self.logger.info(f"✅ 通过: {passed_tests}")
        self.logger.info(f"❌ 失败: {failed_tests}")
        self.logger.info(f"💥 错误: {error_tests}")
        self.logger.info(f"⏭️  跳过: {skipped_tests}")
        
        self.logger.info("\n详细结果:")
        self.logger.info("-" * 40)
        for test_name, result in self.test_results.items():
            status_icon = {
                'PASS': '✅',
                'FAIL': '❌',
                'ERROR': '💥',
                'SKIPPED': '⏭️',
                'TIMEOUT': '⏰',
                'PARTIAL': '⚠️'
            }.get(result, '❓')
            
            self.logger.info(f"{status_icon} {test_name}: {result}")
        
        # 保存测试报告
        report_file = os.path.join(self.temp_dir, f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
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
            self.logger.info(f"\n🎉 测试总体成功! 成功率: {success_rate:.1f}%")
        elif success_rate >= 60:
            self.logger.info(f"\n⚠️  测试部分成功，建议检查失败项。成功率: {success_rate:.1f}%")
        else:
            self.logger.error(f"\n💥 测试失败较多，需要重点修复。成功率: {success_rate:.1f}%")
        
        self.logger.info("=" * 80)

def main():
    """主程序入口"""
    print("🔧 段落层级翻译功能测试工具")
    print("=" * 80)
    
    # 可以通过命令行参数指定PPT文件进行实际测试
    test_ppt_path = None
    if len(sys.argv) > 1:
        test_ppt_path = sys.argv[1]
        print(f"📄 使用命令行指定的PPT文件: {test_ppt_path}")
    
    # 创建测试器并运行测试
    tester = ParagraphTranslationTester()
    results = tester.run_all_tests(test_ppt_path)
    
    # 根据测试结果设置退出码
    failed_count = len([r for r in results.values() if r in ['FAIL', 'ERROR']])
    if failed_count == 0:
        print("\n🎉 所有测试都成功了！")
        sys.exit(0)
    else:
        print(f"\n💥 有 {failed_count} 个测试失败，请检查日志。")
        sys.exit(1)

if __name__ == "__main__":
    main()
