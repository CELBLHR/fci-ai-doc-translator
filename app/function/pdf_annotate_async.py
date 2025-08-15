#!/usr/bin/env python3
"""
PDF注释异步处理模块
支持并发处理PDF注释、OCR识别和翻译
"""
import asyncio
import logging
import os
import base64
import io
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable

import fitz  # PyMuPDF
import easyocr
import numpy as np
from PIL import Image
import aiofiles

# 配置日志
logger = logging.getLogger(__name__)


def make_json_serializable(obj):
    """
    将对象转换为JSON可序列化的格式
    处理numpy类型、复杂嵌套结构等
    """
    if obj is None:
        return None
    elif isinstance(obj, (bool, str)):
        return obj
    elif isinstance(obj, (int, float)):
        return obj
    elif hasattr(obj, 'item'):  # numpy标量
        return obj.item()
    elif hasattr(obj, 'tolist'):  # numpy数组
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    else:
        # 对于其他类型，尝试转换为字符串
        try:
            return float(obj)
        except (ValueError, TypeError):
            return str(obj)

class PDFAnnotationProcessor:
    """PDF注释处理器"""

    def __init__(self, max_workers: int = 4, ocr_languages: list = None):
        """
        初始化PDF注释处理器

        Args:
            max_workers: 最大并发工作线程数
            ocr_languages: OCR识别语言列表，默认为['ch_sim', 'en']
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 设置OCR语言配置
        self.ocr_languages = ocr_languages or ['ch_sim', 'en']

        # 初始化EasyOCR读取器
        # 支持中文和英文识别
        self.ocr_reader = None
        self._init_ocr_reader()

    def _init_ocr_reader(self):
        """
        初始化EasyOCR读取器
        延迟初始化以避免启动时的性能影响
        """
        # 定义语言组合的优先级顺序
        language_combinations = [
            self.ocr_languages,  # 用户指定的语言组合
            ['ch_sim', 'en'],    # 中文简体+英文
            ['ch_tra', 'en'],    # 中文繁体+英文
            ['en'],              # 仅英文
        ]

        # 移除重复的组合
        seen = set()
        unique_combinations = []
        for combo in language_combinations:
            combo_tuple = tuple(sorted(combo))
            if combo_tuple not in seen:
                seen.add(combo_tuple)
                unique_combinations.append(combo)

        for i, languages in enumerate(unique_combinations):
            try:
                logger.info(f"尝试初始化EasyOCR，语言: {languages}")
                self.ocr_reader = easyocr.Reader(languages, gpu=False)

                # 保存成功初始化的语言列表
                self._current_languages = languages

                logger.info(f" EasyOCR读取器初始化成功，语言: {languages}")
                return
            except Exception as e:
                logger.warning(f"语言组合 {languages} 初始化失败: {str(e)}")
                if i == len(unique_combinations) - 1:
                    logger.error("所有语言组合都初始化失败")
                    self.ocr_reader = None
                    self._current_languages = None

    def _get_ocr_reader(self):
        """
        获取OCR读取器，如果未初始化则进行初始化
        """
        if self.ocr_reader is None:
            self._init_ocr_reader()
        return self.ocr_reader

    def get_ocr_info(self):
        """
        获取OCR读取器信息

        Returns:
            Dict: OCR读取器的状态和语言信息
        """
        if self.ocr_reader is None:
            result = {
                'status': 'not_initialized',
                'languages': None,
                'gpu_enabled': False
            }
            return make_json_serializable(result)

        try:
            # 使用保存的语言列表，避免访问可能不存在的属性
            languages = getattr(self, '_current_languages', self.ocr_languages)

            # 安全地检查GPU状态
            gpu_enabled = False
            try:
                # 方法1: 检查device属性
                if hasattr(self.ocr_reader, 'device'):
                    device_str = str(self.ocr_reader.device).lower()
                    gpu_enabled = 'cuda' in device_str or 'gpu' in device_str
                # 方法2: 检查detector的device属性
                elif hasattr(self.ocr_reader, 'detector') and hasattr(self.ocr_reader.detector, 'device'):
                    device_str = str(self.ocr_reader.detector.device).lower()
                    gpu_enabled = 'cuda' in device_str or 'gpu' in device_str
                # 方法3: 检查gpu属性
                elif hasattr(self.ocr_reader, 'gpu'):
                    gpu_enabled = bool(self.ocr_reader.gpu)
            except Exception as gpu_e:
                logger.debug(f"检查GPU状态时出错: {str(gpu_e)}")
                gpu_enabled = False

            result = {
                'status': 'ready',
                'languages': languages,
                'gpu_enabled': gpu_enabled
            }
            return make_json_serializable(result)
        except Exception as e:
            logger.error(f"获取OCR信息时出错: {str(e)}")
            error_result = {
                'status': 'error',
                'error': str(e),
                'languages': getattr(self, '_current_languages', None),
                'gpu_enabled': False
            }
            return make_json_serializable(error_result)

    async def process_pdf_annotations(
        self,
        pdf_path: str,
        annotations: List[Dict[str, Any]],
        output_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        异步处理PDF注释

        Args:
            pdf_path: PDF文件路径
            annotations: 注释列表
            output_path: 输出文件路径
            progress_callback: 进度回调函数

        Returns:
            bool: 处理是否成功
        """
        try:
            logger.info(f"开始处理PDF注释: {pdf_path}")
            logger.info(f"注释数量: {len(annotations)}")

            # 在线程池中执行PDF处理
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._process_pdf_sync,
                pdf_path,
                annotations,
                output_path,
                progress_callback
            )

            logger.info(f"PDF注释处理完成: {output_path}")
            return result

        except Exception as e:
            logger.error(f"PDF注释处理失败: {str(e)}")
            return False

    def _process_pdf_sync(
        self,
        pdf_path: str,
        annotations: List[Dict[str, Any]],
        output_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        同步处理PDF注释（在线程池中执行）

        Args:
            pdf_path: PDF文件路径
            annotations: 注释列表
            output_path: 输出文件路径
            progress_callback: 进度回调函数

        Returns:
            bool: 处理是否成功
        """
        try:
            # 打开PDF文档
            doc = fitz.open(pdf_path)
            total_annotations = len(annotations)

            logger.info(f"PDF文档打开成功，总页数: {doc.page_count}")

            # 处理每个注释
            for i, annotation in enumerate(annotations):
                try:
                    page_num = annotation.get('page', 1) - 1  # 转换为0基索引

                    if page_num < 0 or page_num >= doc.page_count:
                        logger.warning(f"页面索引超出范围: {page_num + 1}, 跳过此注释")
                        continue

                    # 获取页面
                    page = doc.load_page(page_num)

                    # 获取注释坐标
                    coords = annotation.get('coords', {})
                    left = coords.get('left', 0)
                    top = coords.get('top', 0)
                    width = coords.get('width', 0)
                    height = coords.get('height', 0)

                    # 创建矩形区域
                    rect = fitz.Rect(left, top, left + width, top + height)

                    # 添加高亮注释
                    highlight = page.add_highlight_annot(rect)

                    # 设置注释内容
                    text = annotation.get('text', '')
                    ocr_result = annotation.get('ocrResult', '')
                    translation = annotation.get('translation', '')

                    # 组合注释内容
                    content_parts = []
                    if ocr_result:
                        content_parts.append(f"OCR: {ocr_result}")
                    if translation:
                        content_parts.append(f"翻译: {translation}")
                    if text and text != ocr_result:
                        content_parts.append(f"备注: {text}")

                    content = "\n".join(content_parts) if content_parts else "注释"
                    highlight.set_content(content)

                    # 更新注释
                    highlight.update()

                    logger.info(f"处理注释 {i + 1}/{total_annotations}: 页面 {page_num + 1}")

                    # 更新进度
                    if progress_callback:
                        progress_callback(i + 1, total_annotations)

                except Exception as e:
                    logger.error(f"处理注释 {i + 1} 时出错: {str(e)}")
                    continue

            # 保存PDF文档
            doc.save(output_path)
            doc.close()

            logger.info(f"PDF注释处理完成，已保存到: {output_path}")
            return True

        except Exception as e:
            logger.error(f"PDF注释处理失败: {str(e)}")
            return False

    async def ocr_image_region(
        self,
        image_data: str,
        language: str = 'auto'
    ) -> Dict[str, Any]:
        """
        异步OCR图像区域识别

        Args:
            image_data: base64编码的图像数据
            language: OCR识别语言

        Returns:
            Dict: OCR识别结果
        """
        try:
            # 在线程池中执行OCR
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._ocr_image_sync,
                image_data,
                language
            )

            return result

        except Exception as e:
            logger.error(f"OCR识别失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'text': ''
            }

    def _ocr_image_sync(
        self,
        image_data: str,
        language: str = 'auto'
    ) -> Dict[str, Any]:
        """
        同步OCR图像识别（在线程池中执行）
        使用EasyOCR进行文字识别

        Args:
            image_data: base64编码的图像数据
            language: OCR识别语言 (EasyOCR会自动检测)

        Returns:
            Dict: OCR识别结果
        """
        try:
            # 获取OCR读取器
            reader = self._get_ocr_reader()
            if reader is None:
                raise Exception("EasyOCR读取器未初始化")

            # 解码base64图像数据
            if ',' in image_data:
                image_data = image_data.split(',')[1]  # 移除data:image/png;base64,前缀

            image_bytes = base64.b64decode(image_data)

            # 将图像数据转换为PIL Image对象
            image = Image.open(io.BytesIO(image_bytes))

            # 转换为numpy数组 (EasyOCR需要numpy数组)
            image_np = np.array(image)

            # 使用EasyOCR进行识别
            # EasyOCR返回的是 [(bbox, text, confidence), ...]
            results = reader.readtext(image_np)

            # 提取所有识别到的文本
            texts = []
            confidences = []
            serializable_results = []

            for (bbox, text, confidence) in results:
                if confidence > 0.1:  # 只保留置信度大于0.1的结果
                    texts.append(text.strip())
                    confidences.append(float(confidence))  # 转换为Python float

                    # 转换bbox为JSON可序列化的格式
                    serializable_bbox = []
                    for point in bbox:
                        serializable_point = [float(point[0]), float(point[1])]
                        serializable_bbox.append(serializable_point)

                    serializable_results.append({
                        'bbox': serializable_bbox,
                        'text': text.strip(),
                        'confidence': float(confidence)
                    })

            # 合并所有文本
            combined_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            logger.info(f"EasyOCR识别完成，文本长度: {len(combined_text)}, 平均置信度: {avg_confidence:.2f}")
            logger.info(f"识别到的文本: {combined_text[:100]}...")  # 只显示前100个字符

            # 使用工具函数确保所有数据都是JSON可序列化的
            result = {
                'success': True,
                'text': combined_text,
                'confidence': avg_confidence,
                'details': serializable_results,
                'error': None
            }

            return make_json_serializable(result)

        except Exception as e:
            logger.error(f"EasyOCR识别失败: {str(e)}")
            error_result = {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0.0,
                'details': []
            }
            return make_json_serializable(error_result)

    async def extract_pdf_annotations(
        self,
        pdf_path: str
    ) -> List[Dict[str, Any]]:
        """
        异步提取PDF中的现有注释

        Args:
            pdf_path: PDF文件路径

        Returns:
            List[Dict]: 注释列表
        """
        try:
            # 在线程池中执行注释提取
            loop = asyncio.get_event_loop()
            annotations = await loop.run_in_executor(
                self.executor,
                self._extract_annotations_sync,
                pdf_path
            )

            return annotations

        except Exception as e:
            logger.error(f"提取PDF注释失败: {str(e)}")
            return []

    def _extract_annotations_sync(
        self,
        pdf_path: str
    ) -> List[Dict[str, Any]]:
        """
        同步提取PDF注释（在线程池中执行）

        Args:
            pdf_path: PDF文件路径

        Returns:
            List[Dict]: 注释列表
        """
        try:
            annotations = []
            doc = fitz.open(pdf_path)

            # 遍历每一页
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                page_annotations = page.annots()

                if page_annotations:
                    for annot in page_annotations:
                        # 获取注释信息
                        rect = annot.rect
                        content = annot.content
                        annot_type = annot.type[1]  # 注释类型名称

                        annotation = {
                            'page': page_num + 1,
                            'type': annot_type,
                            'coords': {
                                'left': rect.x0,
                                'top': rect.y0,
                                'width': rect.x1 - rect.x0,
                                'height': rect.y1 - rect.y0
                            },
                            'content': content,
                            'text': content
                        }

                        annotations.append(annotation)

            doc.close()
            logger.info(f"提取到 {len(annotations)} 个注释")
            return annotations

        except Exception as e:
            logger.error(f"提取PDF注释失败: {str(e)}")
            return []

    async def save_annotations_to_file(
        self,
        annotations: List[Dict[str, Any]],
        file_path: str,
        user_info: Dict[str, Any] = None
    ) -> bool:
        """
        异步保存注释到文件

        Args:
            annotations: 注释列表
            file_path: 保存文件路径
            user_info: 用户信息

        Returns:
            bool: 保存是否成功
        """
        try:
            # 准备保存数据
            save_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user': user_info.get('username', 'unknown') if user_info else 'unknown',
                'annotations': annotations,
                'total_count': len(annotations)
            }

            # 异步写入文件
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(save_data, ensure_ascii=False, indent=2))

            logger.info(f"注释已保存到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"保存注释失败: {str(e)}")
            return False

    async def load_annotations_from_file(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        异步从文件加载注释

        Args:
            file_path: 注释文件路径

        Returns:
            Dict: 注释数据
        """
        try:
            # 异步读取文件
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)

            logger.info(f"从文件加载了 {len(data.get('annotations', []))} 个注释")
            return data

        except Exception as e:
            logger.error(f"加载注释失败: {str(e)}")
            return {'annotations': [], 'error': str(e)}

    def close(self):
        """关闭处理器"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
            logger.info("PDF注释处理器已关闭")


# 全局PDF注释处理器实例
pdf_processor = PDFAnnotationProcessor()


async def process_pdf_annotations_async(
    pdf_path: str,
    annotations: List[Dict[str, Any]],
    output_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """
    异步处理PDF注释的便捷函数

    Args:
        pdf_path: PDF文件路径
        annotations: 注释列表
        output_path: 输出文件路径
        progress_callback: 进度回调函数

    Returns:
        bool: 处理是否成功
    """
    return await pdf_processor.process_pdf_annotations(
        pdf_path, annotations, output_path, progress_callback
    )


async def ocr_image_region_async(
    image_data: str,
    language: str = 'auto'
) -> Dict[str, Any]:
    """
    异步OCR图像区域识别的便捷函数
    使用EasyOCR进行文字识别

    Args:
        image_data: base64编码的图像数据
        language: OCR识别语言 (EasyOCR自动检测)

    Returns:
        Dict: OCR识别结果，包含text、confidence等信息
    """
    return await pdf_processor.ocr_image_region(image_data, language)
