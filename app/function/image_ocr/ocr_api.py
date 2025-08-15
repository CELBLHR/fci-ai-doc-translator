import requests
import time
import os
import zipfile
import json
import platform
import subprocess
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 导入日志系统
from logger_config_ocr import get_logger

# 获取日志记录器
logger = get_logger("ocr_api")

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

    def batch_process_folder(self, folder_path):
        """批量处理文件夹中的所有PDF文件"""
        if not os.path.exists(folder_path):
            logger.error(f"❌ 文件夹不存在: {folder_path}")
            return
        
        # 获取文件夹中所有的PDF和EMF文件
        supported_files = []
        temp_converted_files = []  # 记录临时转换的文件，以便后续清理
        
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            
            # 检查是否为支持的文件格式
            if file_name.lower().endswith(('.pdf', '.png','.jpg')):
                supported_files.append(file_path)
            elif file_name.lower().endswith('.emf'):
                # 对于EMF文件，先转换再添加
                converted_file = self.convert_emf_file(file_path)
                if converted_file:
                    supported_files.append(converted_file)
                    temp_converted_files.append(converted_file)  # 记录以便清理
        
        if not supported_files:
            logger.error(f"❌ 文件夹中没有找到支持的文件: {folder_path}")
            return
        
        logger.info(f"📁 找到 {len(supported_files)} 个支持的文件，准备批量处理")
        
        try:
            # 调用批量处理方法
            result = self.batch_process_pdfs(supported_files)
            return result
        finally:
            # 清理临时转换的文件
            self.cleanup_temp_files(temp_converted_files)
    
    def convert_emf_file(self, emf_path):
        """
        转换EMF文件为PNG或PDF（优先转换为PNG）
        
        Args:
            emf_path (str): EMF文件路径
            
        Returns:
            str: 转换后的文件路径，失败返回None
        """
        try:
            base_name = os.path.splitext(os.path.basename(emf_path))[0]
            folder_path = os.path.dirname(emf_path)
            
            # 优先尝试转换为PNG（更简单直接）
            png_path = os.path.join(folder_path, f"{base_name}.png")
            if self.convert_emf_to_png(emf_path, png_path):
                return png_path
            
            # 如果PNG转换失败，尝试转换为PDF
            pdf_path = os.path.join(folder_path, f"{base_name}.pdf")
            if self.convert_emf_to_pdf(emf_path, pdf_path):
                return pdf_path
                
            logger.error(f"❌ 无法转换EMF文件: {emf_path}")
            return None
        except Exception as e:
            logger.error(f"❌ 转换EMF文件时出错: {e}")
            return None
    
    def cleanup_temp_files(self, temp_files):
        """
        清理临时转换的文件
        
        Args:
            temp_files (list): 临时文件路径列表
        """
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"🧹 已清理临时文件: {file_path}")
            except Exception as e:
                logger.error(f"⚠️ 清理临时文件失败 {file_path}: {e}")

    def check_batch_status(self, batch_id):
        """检查批次处理状态"""
        try:
            url = f'https://mineru.net/api/v4/extract-results/batch/{batch_id}'
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=(30, 60)
            )
            
            if response.status_code == 200:
                return response.json()["data"]
            else:
                logger.error(f"检查批次状态失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"检查批次状态时发生错误: {str(e)}")
            return None

    def wait_and_download_batch_results(self, batch_id, check_interval=30):
        """
        等待批次处理完成并下载结果
        
        Args:
            batch_id (str): 批次ID
            check_interval (int): 检查间隔（秒）
        """
        logger.info(f"⏳ 等待批次 {batch_id} 处理完成...")
        
        while True:
            # 获取当前批次状态
            data = self.check_batch_status(batch_id)
            if not data:
                logger.error(f"❌ 无法获取批次 {batch_id} 状态")
                return
            
            # 统计处理进度
            extract_results = data.get('extract_result', [])
            done_count = sum(1 for item in extract_results if item.get('state') == 'done')
            failed_count = sum(1 for item in extract_results if item.get('state') == 'failed')
            total_count = len(extract_results)
            
            logger.info(f"📊 处理中: {done_count}/{total_count} 已完成, {failed_count} 失败")
            
            # 如果所有文件都处理完毕（完成或失败），则退出循环
            if done_count + failed_count == total_count:
                logger.info("✅ 批次处理完成，开始下载结果...")
                self.download_batch_results(data)
                return
            
            # 等待指定时间后再次检查
            time.sleep(check_interval)

    def extract_and_cleanup_zip(self, zip_path, output_dir=None):
        """
        解压zip文件到同名文件夹并删除原文件
        
        Args:
            zip_path (str): zip文件路径
            output_dir (str): 解压根目录
        """
        if output_dir is None:
            output_dir = os.path.join(self.pdf_folder, "batch_results")
        try:
            # 创建与zip文件同名的文件夹
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            extract_folder = os.path.join(output_dir, zip_name)
            os.makedirs(extract_folder, exist_ok=True)
            
            # 解压zip文件到同名文件夹
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            logger.info(f"✅ 已解压到文件夹: {extract_folder}")
            
            # 删除zip文件
            os.remove(zip_path)
            logger.info(f"🧹 已删除: {zip_path}")
            
        except zipfile.BadZipFile as e:
            logger.error(f"❌ ZIP文件损坏 {zip_path}: {str(e)}")
            # 尝试删除损坏的文件
            try:
                os.remove(zip_path)
                logger.info(f"🧹 已删除损坏的文件: {zip_path}")
            except:
                pass
        except Exception as e:
            logger.error(f"❌ 解压或删除失败 {zip_path}: {str(e)}")

    def download_batch_results(self, batch_data):
        """
        下载批次处理结果
        
        Args:
            batch_data (dict): 批次处理结果数据
        """
        extract_results = batch_data.get('extract_result', [])
        success_count = 0
        
        # 创建结果目录（始终在pdf_folder下）
        output_dir = os.path.join(self.pdf_folder, "batch_results")
        os.makedirs(output_dir, exist_ok=True)
        
        for item in extract_results:
            if item.get('state') == 'done' and 'full_zip_url' in item:
                zip_url = item['full_zip_url']
                original_name = item['file_name']
                
                try:
                    # 安全地获取data_id，如果不存在则使用文件名作为替代
                    data_id = item.get('data_id')
                    if not data_id:
                        # 如果没有data_id，使用文件名的一部分作为标识
                        data_id = os.path.splitext(original_name)[0]
                        logger.warning(f"⚠️ 文件 {original_name} 缺少data_id，使用文件名作为替代: {data_id}")
                    
                    # 生成输出文件路径
                    base_name = os.path.splitext(original_name)[0]
                    final_filename = f"{base_name}.md"
                    output_path = os.path.join(output_dir, final_filename)
                    
                    # 下载ZIP文件，使用data_id或替代标识作为文件名
                    logger.info(f"📥 正在下载: {original_name}")
                    
                    # 尝试HTTPS下载
                    try:
                        zip_response = self.session.get(
                            zip_url, 
                            stream=True,
                            timeout=(30, 300)
                        )
                        zip_response.raise_for_status()
                    except requests.exceptions.SSLError:
                        # 如果HTTPS失败，尝试HTTP
                        logger.warning(f"⚠️ HTTPS下载失败，尝试HTTP...")
                        http_url = zip_url.replace('https://', 'http://')
                        zip_response = self.session.get(
                            http_url, 
                            stream=True,
                            timeout=(30, 300)
                        )
                        zip_response.raise_for_status()
                    
                    # 保存ZIP文件
                    zip_path = os.path.join(output_dir, f"{data_id}.zip")
                    with open(zip_path, 'wb') as f:
                        for chunk in zip_response.iter_content(1024 * 1024):
                            if chunk:  # 过滤掉keep-alive chunks
                                f.write(chunk)
                    
                    logger.info(f"✅ {original_name} 下载完成")
                    
                    # 解压并删除zip文件
                    self.extract_and_cleanup_zip(zip_path, output_dir)
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ 下载失败: {original_name} | 错误: {str(e)}")
        
        logger.info(f"🏁 批量下载完成，成功下载 {success_count}/{len(extract_results)} 个文件")
        
        # 添加文本数据到原始image_mapping.json文件
        if self.pdf_folder and os.path.exists(self.pdf_folder):
            mapping_file_path = os.path.join(self.pdf_folder, "image_mapping.json")
            if os.path.exists(mapping_file_path):
                self.collect_and_merge_text_to_mapping(mapping_file_path, output_dir)
            else:
                logger.warning(f"⚠️ 未找到映射文件: {mapping_file_path}")
        else:
            logger.warning("⚠️ 未设置pdf_folder或文件夹不存在")

    def collect_and_merge_text_to_mapping(self, source_mapping_file, batch_results_dir=None):
        """
        收集处理后的文本数据并合并到原始的image_mapping.json文件中
        
        Args:
            source_mapping_file (str): 原始image_mapping.json文件路径
            batch_results_dir (str): 批处理结果目录
        """
        if batch_results_dir is None:
            batch_results_dir = os.path.join(self.pdf_folder, "batch_results")
        logger.info(f"🔍 开始收集文本数据...")
        logger.info(f"📁 批处理结果目录: {batch_results_dir}")
        logger.info(f"📄 映射文件路径: {source_mapping_file}")
        
        # 检查结果目录是否存在
        if not os.path.exists(batch_results_dir):
            logger.error(f"❌ 结果目录不存在: {batch_results_dir}")
            return
        
        # 读取原始image_mapping.json文件
        try:
            with open(source_mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            logger.info(f"✅ 成功读取映射文件")
        except Exception as e:
            logger.error(f"❌ 无法读取原始映射文件 {source_mapping_file}: {e}")
            return
        
        # 遍历处理结果目录中的所有文件夹，收集文本数据
        text_mapping = {}
        
        logger.info(f"📂 查找结果文件夹中的content_list.json文件...")
        for folder_name in os.listdir(batch_results_dir):
            folder_path = os.path.join(batch_results_dir, folder_name)
            
            # 确保是目录
            if not os.path.isdir(folder_path):
                continue
                
            logger.info(f"📁 检查文件夹: {folder_name}")
            
            # 查找生成的content_list.json文件（处理结果）
            content_list_json_path = None
            for file in os.listdir(folder_path):
                if file.endswith('_content_list.json'):
                    content_list_json_path = os.path.join(folder_path, file)
                    logger.info(f"📄 找到content_list文件: {file}")
                    break
            
            if not content_list_json_path or not os.path.exists(content_list_json_path):
                logger.warning(f"⚠️ 未找到处理后的content_list.json文件: {folder_name}")
                continue
                
            # 读取处理后的JSON文件
            try:
                with open(content_list_json_path, 'r', encoding='utf-8') as f:
                    content_data = json.load(f)
                logger.info(f"✅ 成功读取 {content_list_json_path}")
            except Exception as e:
                logger.error(f"❌ 无法读取处理后的JSON文件 {content_list_json_path}: {e}")
                continue
                
            # 提取文本内容
            all_text = self._extract_text_from_content_list(content_data)
            
            if not all_text:
                logger.warning(f"⚠️ 从 {folder_name} 中未提取到文本内容")
                continue
                
            # 使用文件夹名作为键存储文本数据
            text_mapping[folder_name] = all_text
            logger.info(f"✅ 已提取 {folder_name} 的文本数据，共 {len(all_text)} 条文本")
        
        logger.info(f"📊 共收集到 {len(text_mapping)} 个文件的文本数据")
        
        # 将文本数据映射到image_mapping.json中
        updated_count = 0
        logger.info(f"🔄 开始将文本数据映射到image_mapping.json中...")
        
        for slide_key, slide_data in mapping_data.items():
            if 'images' in slide_data:
                for image_info in slide_data['images']:
                    filename = image_info.get('filename')
                    if filename:
                        # 不再移除文件扩展名，而是尝试多种匹配方式
                        name_without_ext = os.path.splitext(filename)[0]
                        logger.info(f"🔍 匹配文件名: {filename} -> 尝试匹配 {filename} 或 {name_without_ext}")
                        
                        # 尝试多种匹配方式
                        matched = False
                        # 方式1: 完全匹配（包含扩展名）
                        if filename in text_mapping:
                            image_info['all_text'] = text_mapping[filename]
                            updated_count += 1
                            matched = True
                            logger.info(f"✅ 通过完整文件名 {filename} 匹配成功")
                        # 方式2: 去掉扩展名匹配
                        elif name_without_ext in text_mapping:
                            image_info['all_text'] = text_mapping[name_without_ext]
                            updated_count += 1
                            matched = True
                            logger.info(f"✅ 通过文件名(无扩展名) {name_without_ext} 匹配成功")
                        # 方式3: 如果结果文件夹名与filename完全一致
                        else:
                            # 检查是否存在与filename完全一致的文件夹
                            full_path = os.path.join(batch_results_dir, filename)
                            if os.path.exists(full_path) and os.path.isdir(full_path):
                                # 在该文件夹中查找content_list.json
                                content_list_path = None
                                for file in os.listdir(full_path):
                                    if file.endswith('_content_list.json'):
                                        content_list_path = os.path.join(full_path, file)
                                        break
                                
                                if content_list_path and os.path.exists(content_list_path):
                                    try:
                                        with open(content_list_path, 'r', encoding='utf-8') as f:
                                            content_data = json.load(f)
                                        all_text = self._extract_text_from_content_list(content_data)
                                        if all_text:
                                            image_info['all_text'] = all_text
                                            updated_count += 1
                                            matched = True
                                            logger.info(f"✅ 通过目录匹配 {filename} 成功")
                                    except Exception as e:
                                        logger.error(f"❌ 读取 {content_list_path} 时出错: {e}")
                        
                        if not matched:
                            logger.warning(f"⚠️ 未找到 {filename} 对应的文本数据")
        
        logger.info(f"📝 共更新了 {updated_count} 个图像条目")
        
        # 将更新后的数据写回image_mapping.json
        try:
            with open(source_mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mapping_data, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 成功更新 {updated_count} 个图像条目，文本数据已添加到 {source_mapping_file}")
        except Exception as e:
            logger.error(f"❌ 无法写入更新后的数据到 {source_mapping_file}: {e}")

    def _extract_text_from_content_list(self, content_data):
        """
        从content_list数据中提取所有文本内容
        
        Args:
            content_data (list): content_list数据
            
        Returns:
            dict: 包含所有文本的字典，格式为 {"text1": "...", "text2": "..."}
        """
        texts = []
        
        # 遍历content_list中的所有条目
        for item in content_data:
            if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                text_value = item['text']
                if isinstance(text_value, str) and text_value.strip():
                    texts.append(text_value.strip())
        
        # 构造all_text字典
        all_text = {}
        for i, text in enumerate(texts, 1):
            all_text[f"text{i}"] = text
            
        return all_text


#api token 14天一换
TOKEN = os.getenv("OCR_TOKEN")

# 处理文件夹（现在也支持EMF文件）
pdf_folder = "/tmp/ppt_ocr_0xq_xja2" # 修改为你的文件夹路径
processor = OCRProcessor(TOKEN, pdf_folder)
processor.batch_process_folder(pdf_folder)