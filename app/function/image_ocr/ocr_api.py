#!/usr/bin/env python3
"""
MinerU API接口实现
用于PDF文档的OCR识别和内容提取
"""

import os
import time
import requests
import logging
import zipfile
from pathlib import Path
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 修复logger_config_ocr导入问题
try:
    from .logger_config_ocr import setup_logger
    logger = setup_logger('MinerUAPI')
except (ImportError, ModuleNotFoundError):
    # 如果无法导入自定义日志配置，则使用默认日志配置
    logger = logging.getLogger('MinerUAPI')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

try:
    import zlib
    compression = zipfile.ZIP_DEFLATED
except:
    compression = zipfile.ZIP_STORED

# 添加项目根目录到Python路径，确保可以导入logger_config_ocr
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
import sys
sys.path.insert(0, str(project_root))

# 尝试导入日志配置
try:
    from .logger_config_ocr import setup_logger
    logger = setup_logger("mineru_api")
except ImportError:
    # 如果无法导入自定义日志配置，则使用默认配置
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

class MinerUAPI:
    """MinerU API接口类"""
    
    def __init__(self):
        self.token = os.getenv('MINERU_API_KEY')
        if not self.token:
            raise ValueError("MINERU_API_KEY环境变量未设置")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'User-Agent': 'FCIAI2.0/1.0'
        })
    
    def process_pdf(self, file_path):
        """处理本地PDF文件"""
        # 1. 上传文件
        logger.info(f"开始上传PDF文件: {file_path}")
        pdf_url = self.upload_file(file_path)
        if not pdf_url:
            logger.error("文件上传失败")
            return None
        
        logger.info(f"文件上传成功，URL: {pdf_url}")
        
        # 2. 创建MinerU任务
        logger.info("📄 创建解析任务...")
        task_url = 'https://mineru.net/api/v4/extract/task'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        data = {
            'url': pdf_url,
            'is_ocr': True,
            'enable_formula': True,
            'enable_table': True,
            'language': 'auto'
        }
        
        try:
            logger.info("发送创建任务请求...")
            response = self.session.post(
                task_url, 
                headers=headers, 
                json=data,
                timeout=(30, 60)
            )
            result = response.json()
            
            if result['code'] != 0:
                logger.error(f"❌ 创建任务失败: {result['msg']}")
                return None
            
            task_id = result['data']['task_id']
            logger.info(f"✅ 任务ID: {task_id}")
            
            # 3. 等待处理完成
            logger.info("⏳ 等待处理...")
            return self._wait_for_task_completion(task_id, headers)
        except Exception as e:
            logger.error(f"❌ 创建任务时出错: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    def _wait_for_task_completion(self, task_id, headers):
        """等待任务完成"""
        task_url = f'https://mineru.net/api/v4/extract/task/{task_id}'
        max_attempts = 60  # 最多尝试60次，每次间隔5秒，总共300秒(5分钟)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                attempt += 1
                logger.info(f"检查任务状态 (尝试 {attempt}/{max_attempts})")
                status_response = self.session.get(
                    task_url, 
                    headers=headers,
                    timeout=(30, 60)
                )
                status_data = status_response.json()
                logger.info(f"任务状态响应: {status_data}")
                
                if 'data' not in status_data or 'state' not in status_data['data']:
                    logger.error(f"❌ 任务状态响应格式不正确: {status_data}")
                    return None
                
                state = status_data['data']['state']
                logger.info(f"当前任务状态: {state}")
                
                if state == 'done':
                    if 'full_zip_url' not in status_data['data']:
                        logger.error("任务完成但缺少下载URL")
                        return None
                    zip_url = status_data['data']['full_zip_url']
                    logger.info(f"✅ 处理完成！")
                    logger.info(f"📦 下载地址: {zip_url}")
                    return status_data
                    
                elif state == 'failed':
                    err_msg = status_data['data'].get('err_msg', '未知错误')
                    logger.error(f"❌ 处理失败: {err_msg}")
                    return None
                    
                elif state == 'running':
                    progress = status_data['data'].get('extract_progress', {})
                    extracted = progress.get('extracted_pages', 0)
                    total = progress.get('total_pages', 0)
                    logger.info(f"⏳ 正在处理... {extracted}/{total} 页")
                    
                else:
                    logger.info(f"📊 状态: {state}")
                    
                # 等待5秒后再次检查
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ 检查任务状态时出错: {e}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                # 继续尝试而不是直接返回
                
        logger.error("任务等待超时")
        return None
    
    def upload_file(self, file_path):
        """上传本地文件到临时存储"""
        logger.info(f"📤 正在上传文件: {os.path.basename(file_path)}")
        logger.info(f"文件大小: {os.path.getsize(file_path)} 字节")
        
        # 验证文件是否存在且可读
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None
            
        if not os.path.isfile(file_path):
            logger.error(f"路径不是文件: {file_path}")
            return None
            
        # 检查文件是否为空
        if os.path.getsize(file_path) == 0:
            logger.error(f"文件为空: {file_path}")
            return None
        
        # 使用 tmpfiles.org
        try:
            logger.info("准备上传到 tmpfiles.org")
            with open(file_path, 'rb') as f:
                # 明确指定文件名和内容类型
                filename = os.path.basename(file_path)
                files = {'file': (filename, f, 'application/pdf')}
                logger.info(f"发送上传请求，文件名: {filename}")
                
                response = self.session.post(
                    'https://tmpfiles.org/api/v1/upload',
                    files=files,
                    timeout=(30, 60)
                )
                logger.info(f"上传响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"上传响应内容: {result}")
                    # 获取直接下载链接
                    if 'data' in result and 'url' in result['data']:
                        url = result['data']['url']
                        # 注意：tmpfiles.org的直接下载链接格式可能需要调整
                        direct_url = url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                        logger.info(f"✅ 上传成功: {direct_url}")
                        return direct_url
                    else:
                        logger.error(f"上传响应格式不正确: {result}")
                        return None
                else:
                    logger.error(f"上传失败，状态码: {response.status_code}, 响应: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"❌ 上传失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
        
        return None
    
    def download_result(self, zip_url, task_id):
        """下载结果文件"""
        save_path = f"mineru_result_{task_id}.zip"
        
        try:
            response = self.session.get(
                zip_url, 
                stream=True,
                timeout=(30, 300)
            )
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # 过滤掉keep-alive chunks
                        f.write(chunk)
            logger.info(f"✅ 结果已保存到: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            return None

# 导入日志系统
try:
    from .logger_config_ocr import get_logger
    # 获取日志记录器
    logger = get_logger("ocr_api")
except (ImportError, ModuleNotFoundError):
    # 如果无法导入自定义日志配置，则使用默认日志配置
    import logging
    logger = logging.getLogger("ocr_api")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

class OCRProcessor:
    def __init__(self, token, pdf_folder=None):
        self.token = token
        self.pdf_folder = pdf_folder
        self.session = self._create_session()
        self.headers = {
            'Authorization': f'Bearer {token}'
        }
    
    def _create_session(self):
        """创建带重试机制的会话"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504, 521, 522, 524],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def convert_emf_to_png(self, emf_path, png_path):
        """
        将EMF文件转换为PNG格式
        支持Windows和Linux系统
        """
        system = platform.system().lower()
        
        if system == 'windows':
            # Windows平台使用原有方法
            try:
                # 使用PIL尝试打开EMF文件
                image = Image.open(emf_path)
                # 保存为PNG格式
                image.save(png_path, 'PNG')
                logger.info(f"✅ EMF文件已转换为PNG: {png_path}")
                return True
            except Exception as e:
                logger.error(f"❌ EMF转换PNG失败: {e}")
                return False
        else:
            # Linux/Mac平台使用替代方案
            # 尝试使用Inkscape
            if self._convert_emf_to_png_inkscape(emf_path, png_path):
                return True
            # 尝试使用LibreOffice
            elif self._convert_emf_to_png_libreoffice(emf_path, png_path):
                return True
            else:
                logger.error(f"❌ 在{system}系统上无法转换EMF文件: {emf_path}")
                return False
    
    def _convert_emf_to_png_inkscape(self, emf_path, png_path):
        """
        使用Inkscape转换EMF到PNG
        需要安装: sudo apt-get install inkscape
        """
        try:
            cmd = [
                'inkscape',
                emf_path,
                '--export-type=png',
                f'--export-filename={png_path}'
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✅ 使用Inkscape将EMF文件转换为PNG: {png_path}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"⚠️ 使用Inkscape转换EMF失败: {e}")
            return False
    
    def _convert_emf_to_png_libreoffice(self, emf_path, png_path):
        """
        使用LibreOffice转换EMF到PNG
        需要安装: sudo apt-get install libreoffice
        """
        try:
            # 使用libreoffice将EMF转换为PNG
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'png',
                '--outdir', os.path.dirname(png_path),
                emf_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            # LibreOffice会自动命名输出文件，我们需要重命名为目标文件名
            base_name = os.path.splitext(os.path.basename(emf_path))[0]
            auto_generated_path = os.path.join(os.path.dirname(png_path), f"{base_name}.png")
            if os.path.exists(auto_generated_path):
                os.rename(auto_generated_path, png_path)
                logger.info(f"✅ 使用LibreOffice将EMF文件转换为PNG: {png_path}")
                return True
            return False
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"⚠️ 使用LibreOffice转换EMF失败: {e}")
            return False
    
    def convert_emf_to_pdf(self, emf_path, pdf_path):
        """
        将EMF文件转换为PDF格式
        """
        try:
            # 先转换为PNG，再转换为PDF
            image = Image.open(emf_path)
            # 转换为RGB模式（如果需要）
            if image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            
            # 保存为PDF
            image.save(pdf_path, 'PDF', resolution=100.0)
            logger.info(f"✅ EMF文件已转换为PDF: {pdf_path}")
            return True
        except Exception as e:
            logger.error(f"❌ EMF转换PDF失败: {e}")
            return False
    
    def upload_file(self, file_path):
        """上传本地文件到临时存储"""
        logger.info(f"📤 正在上传文件: {os.path.basename(file_path)}")
        
        # 使用 tmpfiles.org
        try:
            with open(file_path, 'rb') as f:
                response = self.session.post(
                    'https://tmpfiles.org/api/v1/upload',
                    files={'file': f},
                    timeout=(30, 60)
                )
                if response.status_code == 200:
                    result = response.json()
                    # 获取直接下载链接
                    url = result['data']['url']
                    direct_url = url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    logger.info(f"✅ 上传成功: {direct_url}")
                    return direct_url
        except Exception as e:
            logger.error(f"❌ 上传失败: {e}")
        
        return None
    
    def process_pdf(self, file_path):
        """处理本地PDF文件"""
        # 1. 上传文件
        pdf_url = self.upload_file(file_path)
        if not pdf_url:
            return None
        
        # 2. 创建MinerU任务
        logger.info("📄 创建解析任务...")
        task_url = 'https://mineru.net/api/v4/extract/task'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        data = {
            'url': pdf_url,
            'is_ocr': True,
            'enable_formula': True,
            'enable_table': True,
            'language': 'auto'
        }
        
        try:
            response = self.session.post(
                task_url, 
                headers=headers, 
                json=data,
                timeout=(30, 60)
            )
            result = response.json()
            
            if result['code'] != 0:
                logger.error(f"❌ 创建任务失败: {result['msg']}")
                return None
            
            task_id = result['data']['task_id']
            logger.info(f"✅ 任务ID: {task_id}")
            
            # 3. 等待处理完成
            logger.info("⏳ 等待处理...")
            return self._wait_for_task_completion(task_id, headers)
        except Exception as e:
            logger.error(f"❌ 创建任务时出错: {e}")
            return None
    
    def _wait_for_task_completion(self, task_id, headers):
        """等待任务完成"""
        task_url = f'https://mineru.net/api/v4/extract/task/{task_id}'
        while True:
            try:
                time.sleep(5)
                status_response = self.session.get(
                    task_url, 
                    headers=headers,
                    timeout=(30, 60)
                )
                status_data = status_response.json()
                
                state = status_data['data']['state']
                
                if state == 'done':
                    zip_url = status_data['data']['full_zip_url']
                    logger.info(f"✅ 处理完成！")
                    logger.info(f"📦 下载地址: {zip_url}")
                    
                    # 下载结果
                    self.download_result(zip_url, task_id)
                    return status_data
                    
                elif state == 'failed':
                    logger.error(f"❌ 处理失败: {status_data['data']['err_msg']}")
                    return None
                    
                elif state == 'running':
                    progress = status_data['data'].get('extract_progress', {})
                    extracted = progress.get('extracted_pages', 0)
                    total = progress.get('total_pages', 0)
                    logger.info(f"⏳ 正在处理... {extracted}/{total} 页")
                
                else:
                    logger.info(f"📊 状态: {state}")
            except Exception as e:
                logger.error(f"❌ 检查任务状态时出错: {e}")
    
    def download_result(self, zip_url, task_id):
        """下载结果文件"""
        save_path = f"mineru_result_{task_id}.zip"
        
        try:
            response = self.session.get(
                zip_url, 
                stream=True,
                timeout=(30, 300)
            )
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # 过滤掉keep-alive chunks
                        f.write(chunk)
            logger.info(f"✅ 结果已保存到: {save_path}")
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")

    def batch_process_pdfs(self, file_paths, data_ids=None):
        """批量处理PDF文件"""
        # 检查文件是否存在
        valid_files = []
        valid_data_ids = []
        
        for i, file_path in enumerate(file_paths):
            if os.path.exists(file_path):
                valid_files.append(file_path)
                if data_ids and i < len(data_ids):
                    valid_data_ids.append(data_ids[i])
                else:
                    # 如果没有提供data_id，则使用文件名作为data_id
                    valid_data_ids.append(os.path.basename(file_path))
            else:
                logger.error(f"❌ 文件不存在: {file_path}")
        
        if not valid_files:
            logger.error("❌ 没有有效的文件可以处理")
            return None
            
        # 准备文件信息
        files_info = []
        file_names = []
        for i, file_path in enumerate(valid_files):
            file_name = os.path.basename(file_path)
            file_names.append(file_name)
            files_info.append({
                "name": file_name,
                "is_ocr": True,
                "data_id": valid_data_ids[i]
            })
        
        # 发送批量处理请求
        logger.info("📄 申请批量处理...")
        batch_url = 'https://mineru.net/api/v4/file-urls/batch'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
        data = {
            "enable_formula": True,
            "language": "auto",
            "enable_table": True,
            "files": files_info
        }
        
        try:
            response = self.session.post(
                batch_url, 
                headers=headers, 
                json=data,
                timeout=(30, 60)
            )
            if response.status_code == 200:
                result = response.json()
                logger.info(f'✅ 批量请求响应: {result}')
                
                if result["code"] == 0:
                    batch_id = result["data"]["batch_id"]
                    urls = result["data"]["file_urls"]
                    logger.info(f'📦 批量ID: {batch_id}')
                    logger.info(f'🔗 上传链接: {urls}')
                    
                    # 上传文件到返回的URL
                    for i, url in enumerate(urls):
                        file_path = valid_files[i]
                        logger.info(f"📤 正在上传: {file_path}")
                        try:
                            with open(file_path, 'rb') as f:
                                res_upload = self.session.put(
                                    url, 
                                    data=f,
                                    timeout=(30, 300)
                                )
                                if res_upload.status_code == 200:
                                    logger.info(f"✅ {file_path} 上传成功")
                                else:
                                    logger.error(f"❌ {file_path} 上传失败, 状态码: {res_upload.status_code}")
                        except Exception as upload_err:
                            logger.error(f"❌ {file_path} 上传过程中出错: {upload_err}")
                        
                        # 在文件上传之间添加延迟，避免服务器压力过大
                        time.sleep(1)
                    
                    logger.info(f"✅ 批量上传完成，批次ID: {batch_id}")
                    
                    # 等待处理完成并下载结果
                    self.wait_and_download_batch_results(batch_id)
                    return batch_id
                else:
                    logger.error(f'❌ 申请上传URL失败: {result["msg"]}')
            else:
                logger.error(f'❌ 请求失败，状态码: {response.status_code}')
                logger.error(f'响应内容: {response.text}')
        except Exception as err:
            logger.error(f"❌ 批量处理出错: {err}")
            
        return None