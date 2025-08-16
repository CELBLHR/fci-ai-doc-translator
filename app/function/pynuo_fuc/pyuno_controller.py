'''
pyuno_controller.py (重构版)
pyuno的总控制器，采用PPTX->ODP->操作->PPTX的流程，移除子进程调用
使用PyUNO接口进行格式转换，确保操作的一致性和可控性
'''
import uno
import json
import os   
import tempfile
from typing import List, Dict
from datetime import datetime
import sys, os
import shutil

sys.path.insert(0, os.path.dirname(__file__))
from logger_config import setup_default_logging, get_logger, log_function_call, log_execution_time
from ppt_data_utils import extract_texts_for_translation, call_translation_api, map_translation_results_back, save_translated_ppt_data


# 直接导入处理函数
from load_ppt_functions import load_entire_ppt_direct
from edit_ppt_functions import write_entire_ppt_direct

# 直接导入处理函数(pptx版本) - 新增
try:
    from edit_ppt_functions_pptx import edit_ppt_with_pptx
except ImportError as e:
    logger = get_logger("pyuno.main")
    logger.error(f"导入PPTX处理模块失败: {str(e)}")
    raise ImportError("请确保 edit_ppt_functions_pptx.py 文件存在并可导入")

import subprocess  # 仍需要用于启动soffice服务
import psutil
import time
import socket

# 移除SOFFICE_PATH，因为格式转换不再使用命令行

def check_port_listening(host='localhost', port=2002, timeout=1):
    """检查指定端口是否正在监听"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, ConnectionRefusedError, OSError):
        return False

def check_soffice_alive():
    """检查soffice进程是否存活"""
    for proc in psutil.process_iter(['name']):
        name = proc.info['name']
        if name and 'soffice' in name.lower():
            return True
    return False

def kill_all_soffice_processes():
    """强制关闭所有 soffice 进程"""
    logger = get_logger("pyuno.main")
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            if name and 'soffice' in name.lower():
                logger.info(f"发现soffice进程 PID {proc.info['pid']}: {name}")
                proc.kill()
                proc.wait(timeout=3)
                killed_count += 1
                logger.info(f"已强制关闭进程 PID {proc.info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            logger.warning(f"无法关闭进程: {e}")
    
    if killed_count > 0:
        logger.info(f"共关闭了 {killed_count} 个soffice进程")
        time.sleep(2)
    
    return killed_count

def wait_for_service_ready(max_wait_seconds=30, check_interval=0.5):
    """等待LibreOffice服务就绪"""
    logger = get_logger("pyuno.main")
    logger.info(f"等待LibreOffice服务端口监听就绪，最多等待 {max_wait_seconds} 秒...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if not check_soffice_alive():
            logger.warning("soffice进程不存在，服务可能启动失败")
            return False
            
        if check_port_listening():
            elapsed = time.time() - start_time
            logger.info(f"LibreOffice服务端口监听就绪！耗时 {elapsed:.1f} 秒")
            return True
            
        time.sleep(check_interval)
    
    logger.error(f"等待 {max_wait_seconds} 秒后，LibreOffice服务端口仍未就绪")
    return False

def start_soffice_service():
    """启动LibreOffice headless服务"""
    logger = get_logger("pyuno.main")
    
    soffice_path = "soffice"  # Ubuntu下默认使用soffice
    # Ubuntu系统的常见路径
    if not os.path.exists(soffice_path) and soffice_path != "soffice":
        possible_paths = [
            "/usr/bin/soffice",
            "/usr/lib/libreoffice/program/soffice",
            "/opt/libreoffice/program/soffice",
            "soffice"
        ]
        
        for path in possible_paths:
            if os.path.exists(path) or path == "soffice":
                soffice_path = path
                logger.info(f"找到soffice路径: {soffice_path}")
                break
        
        if not soffice_path:
            logger.error("未找到soffice可执行文件，请安装LibreOffice")
            return False
    
    soffice_cmd = [
        soffice_path,
        '--headless',
        '--accept=socket,host=localhost,port=2002;urp;',
        '--invisible',
        '--nodefault',
        '--nolockcheck',
        '--nologo',
        '--norestore'
    ]
    
    logger.info(f"启动命令: {' '.join(soffice_cmd)}")
    
    try:
        process = subprocess.Popen(
            soffice_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid  # Linux系统使用
        )
        
        logger.info(f"已启动LibreOffice服务，进程PID: {process.pid}")
        
        if wait_for_service_ready():
            logger.info("LibreOffice headless服务启动成功！")
            return True
        else:
            logger.error("LibreOffice服务启动失败或端口未就绪")
            return False
            
    except Exception as e:
        logger.error(f"启动soffice服务时出错: {e}", exc_info=True)
        return False

def ensure_soffice_running():
    """确保LibreOffice headless服务正在运行"""
    logger = get_logger("pyuno.main")
    
    if check_port_listening():
        logger.info("检测到LibreOffice服务端口正在监听，服务正常")
        return True
    
    if check_soffice_alive():
        logger.warning("检测到soffice进程但端口未监听，可能服务异常，将重启服务")
        kill_all_soffice_processes()
    else:
        logger.warning("未检测到LibreOffice headless服务，准备启动")
    
    logger.info("正在启动LibreOffice headless服务...")
    return start_soffice_service()

def convert_pptx_to_odp_pyuno(pptx_path, output_dir=None):
    """
    使用PyUNO接口将PPTX文件转换为ODP文件
    :param pptx_path: 输入的PPTX文件路径
    :param output_dir: 输出目录（默认为PPTX文件所在目录）
    :return: 转换后ODP文件路径，失败返回None
    """
    logger = get_logger("pyuno.main")
    
    if not os.path.exists(pptx_path):
        logger.error(f"PPTX文件不存在: {pptx_path}")
        return None

    if output_dir is None:
        output_dir = os.path.dirname(pptx_path)

    try:
        logger.info(f"使用PyUNO接口转换PPTX到ODP: {pptx_path}")
        
        # 连接到LibreOffice
        localContext = uno.getComponentContext()
        resolver = localContext.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", localContext)
        context = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        
        # 获取桌面服务
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        
        # 打开PPTX文件
        file_url = uno.systemPathToFileUrl(os.path.abspath(pptx_path))
        logger.debug(f"打开PPTX文件: {file_url}")
        
        # 加载文档时设置为隐藏模式
        props = []
        prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        prop.Name = "Hidden"
        prop.Value = True
        props.append(prop)
        
        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, tuple(props))
        
        if not presentation:
            logger.error("无法加载PPTX文件")
            return None
        
        # 生成ODP输出路径
        base_name = os.path.splitext(os.path.basename(pptx_path))[0]
        odp_path = os.path.join(output_dir, base_name + ".odp")
        output_url = uno.systemPathToFileUrl(os.path.abspath(odp_path))
        
        logger.debug(f"保存为ODP文件: {output_url}")
        
        # 设置保存参数为ODP格式
        save_props = []
        
        # 设置过滤器为ODP格式
        filter_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        filter_prop.Name = "FilterName"
        filter_prop.Value = "impress8"  # ODP格式的过滤器名称
        save_props.append(filter_prop)
        
        # 设置覆盖已存在文件
        overwrite_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        overwrite_prop.Name = "Overwrite"
        overwrite_prop.Value = True
        save_props.append(overwrite_prop)
        
        # 保存为ODP格式
        presentation.storeToURL(output_url, tuple(save_props))
        
        # 关闭文档
        presentation.close(True)
        
        # 验证文件是否创建成功
        if os.path.exists(odp_path):
            logger.info(f"✅ PPTX转ODP成功: {odp_path}")
            return odp_path
        else:
            logger.error("ODP文件保存失败，文件不存在")
            return None
            
    except Exception as e:
        logger.error(f"PyUNO转换PPTX到ODP时出错: {e}", exc_info=True)
        # 尝试关闭可能打开的文档
        try:
            if 'presentation' in locals() and presentation:
                presentation.close(True)
        except:
            pass
        return None

def convert_odp_to_pptx_pyuno(odp_path, output_dir=None):
    """
    使用PyUNO接口将ODP文件转换为PPTX文件
    :param odp_path: 输入的ODP文件路径
    :param output_dir: 输出目录（默认为ODP文件所在目录）
    :return: 转换后PPTX文件路径，失败返回None
    """
    logger = get_logger("pyuno.main")
    
    if not os.path.exists(odp_path):
        logger.error(f"ODP文件不存在: {odp_path}")
        return None

    if output_dir is None:
        output_dir = os.path.dirname(odp_path)

    try:
        logger.info(f"使用PyUNO接口转换ODP到PPTX: {odp_path}")
        
        # 连接到LibreOffice
        localContext = uno.getComponentContext()
        resolver = localContext.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", localContext)
        context = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        
        # 获取桌面服务
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        
        # 打开ODP文件
        file_url = uno.systemPathToFileUrl(os.path.abspath(odp_path))
        logger.debug(f"打开ODP文件: {file_url}")
        
        # 加载文档时设置为隐藏模式
        props = []
        prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        prop.Name = "Hidden"
        prop.Value = True
        props.append(prop)
        
        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, tuple(props))
        
        if not presentation:
            logger.error("无法加载ODP文件")
            return None
        
        # 生成PPTX输出路径
        base_name = os.path.splitext(os.path.basename(odp_path))[0]
        pptx_path = os.path.join(output_dir, base_name + ".pptx")
        output_url = uno.systemPathToFileUrl(os.path.abspath(pptx_path))
        
        logger.debug(f"保存为PPTX文件: {output_url}")
        
        # 设置保存参数为PPTX格式
        save_props = []
        
        # 设置过滤器为PPTX格式
        filter_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        filter_prop.Name = "FilterName"
        filter_prop.Value = "Impress MS PowerPoint 2007 XML"  # PPTX格式的过滤器名称
        save_props.append(filter_prop)
        
        # 设置覆盖已存在文件
        overwrite_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        overwrite_prop.Name = "Overwrite"
        overwrite_prop.Value = True
        save_props.append(overwrite_prop)
        
        # 保存为PPTX格式
        presentation.storeToURL(output_url, tuple(save_props))
        
        # 关闭文档
        presentation.close(True)
        
        # 验证文件是否创建成功
        if os.path.exists(pptx_path):
            logger.info(f"✅ ODP转PPTX成功: {pptx_path}")
            return pptx_path
        else:
            logger.error("PPTX文件保存失败，文件不存在")
            return None
            
    except Exception as e:
        logger.error(f"PyUNO转换ODP到PPTX时出错: {e}", exc_info=True)
        # 尝试关闭可能打开的文档
        try:
            if 'presentation' in locals() and presentation:
                presentation.close(True)
        except:
            pass
        return None

def _validate_and_normalize_page_indices(page_indices):
    """验证和标准化页面索引参数"""
    logger = get_logger("pyuno.main")
    
    if page_indices is None or len(page_indices) == 0:
        logger.info("页面索引参数为空，将处理所有页面")
        return None
    
    try:
        validated_indices = []
        for idx in page_indices:
            if isinstance(idx, (int, str)):
                int_idx = int(idx)
                if int_idx >= 1:
                    internal_index = int_idx - 1  # 1-based转0-based
                    validated_indices.append(internal_index)
                    logger.info(f"用户页面号 {int_idx} -> 内部索引 {internal_index}")
                else:
                    logger.warning(f"忽略无效的页面号（必须>=1）: {int_idx}")
            else:
                logger.warning(f"忽略无效的页面号类型: {type(idx)} -> {idx}")
        
        if not validated_indices:
            logger.warning("所有页面号都无效，将处理所有页面")
            return None
        
        validated_indices = sorted(list(set(validated_indices)))
        user_page_numbers = [idx + 1 for idx in validated_indices]
        logger.info(f"用户选择页面: {user_page_numbers} -> 内部索引: {validated_indices}")
        
        return validated_indices
        
    except Exception as e:
        logger.error(f"验证页面索引时出错: {e}", exc_info=True)
        logger.warning("页面索引验证失败，将处理所有页面")
        return None

def backup_original_pptx(original_path, temp_dir):
    """
    备份原始PPTX文件 - 新增功能
    Args:
        original_path: 原始PPTX文件路径
        temp_dir: 临时目录路径
    Returns:
        backup_path: 备份文件路径
    """
    logger = get_logger("pyuno.main")
    try:
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}_{name}{ext}"
        backup_path = os.path.join(temp_dir, backup_filename)
        
        shutil.copy2(original_path, backup_path)
        logger.info(f"原始PPTX文件已备份到: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"备份PPTX文件失败: {str(e)}")
        raise

# 设置日志记录器
logger = setup_default_logging()

def pyuno_controller(presentation_path: str,
                     stop_words_list: List[str],
                     custom_translations: Dict[str, str],
                     select_page: List[int],
                     source_language: str,
                     target_language: str,
                     bilingual_translation: str,
                     progress_callback,
                     model: str):
    """
    主控制器函数（重构版：PPTX->ODP->操作->PPTX流程）
    """
    start_time = datetime.now()
    
    # 确保soffice服务存活
    ensure_soffice_running()

    log_function_call(logger, "pyuno_controller", 
                     presentation_path=presentation_path,
                     stop_words_list=stop_words_list,
                     custom_translations=custom_translations,
                     select_page=select_page,
                     source_language=source_language,
                     target_language=target_language,
                     bilingual_translation=bilingual_translation,
                     model=model)
    
    logger.info(f"开始处理PPT（重构版 - PPTX->ODP->操作->PPTX，使用PyUNO格式转换）: {presentation_path}")
    logger.info(f"翻译模式: {bilingual_translation}")
    logger.info(f"指定页面: {select_page if select_page else '所有页面'}")
    
    # 检查PPT文件是否存在
    if not os.path.exists(presentation_path):
        logger.error(f"PPT文件不存在: {presentation_path}")
        return None
    
    file_size = os.path.getsize(presentation_path)
    logger.info(f"PPT文件大小: {file_size / (1024*1024):.2f} MB")
    
    # ===== 第零步：创造两个文件分支，一个是ODP，一个是PPTX（新增备份功能） =====
    logger.info("=" * 60)
    logger.info("第0步：创造两个文件分支，一个是ODP，一个是PPTX")
    logger.info("=" * 60)
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="ppt_translate_")
    logger.info(f"创建临时目录: {temp_dir}")
    
    try:
        # 新增：备份原始PPTX文件
        backup_pptx_path = backup_original_pptx(presentation_path, temp_dir)
        
    except Exception as e:
        logger.error(f"备份原始PPTX文件失败: {e}", exc_info=True)
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None
    
    # 将pptx转化为odp，并保存为odp_working_path
    try:
        # 生成ODP文件路径
        input_dir = os.path.dirname(presentation_path)
        input_filename = os.path.splitext(os.path.basename(presentation_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        odp_filename = f"{input_filename}_working_{timestamp}.odp"
        odp_working_path = os.path.join(input_dir, odp_filename)
        
        # 转换PPTX到ODP
        converted_odp_path = convert_pptx_to_odp_pyuno(presentation_path, input_dir)
        
        if not converted_odp_path:
            logger.error("PPTX转ODP失败，无法继续处理")
            # 清理临时目录
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None
        
        # 重命名为工作文件
        if converted_odp_path != odp_working_path:
            os.rename(converted_odp_path, odp_working_path)
            logger.info(f"重命名工作文件: {odp_working_path}")
        
        logger.info(f"✅ PPTX转ODP成功: {odp_working_path}")
        
    except Exception as e:
        logger.error(f"PPTX转ODP过程失败: {e}", exc_info=True)
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None
    
    # ===== 第一步：从ODP加载内容 =====
    logger.info("=" * 60)
    logger.info("第1步：从ODP加载PPT内容")
    logger.info("=" * 60)
    
    try:
        # 验证页面索引
        validated_page_indices = _validate_and_normalize_page_indices(select_page)
        
        # 直接调用加载函数，不使用子进程
        ppt_data = load_entire_ppt_direct(odp_working_path, validated_page_indices)
        
        if not ppt_data:
            logger.error("无法从ODP加载PPT内容")
            # 清理临时ODP文件和临时目录
            if os.path.exists(odp_working_path):
                os.remove(odp_working_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None
        
        # 记录加载信息
        actual_pages = ppt_data.get('pages', [])
        if validated_page_indices:
            logger.info(f"页面选择完成：请求处理页面 {select_page}，实际加载 {len(actual_pages)} 页")
            actual_page_indices = [page.get('page_index', -1) for page in actual_pages]
            logger.info(f"实际处理的页面索引: {actual_page_indices}")
        else:
            logger.info(f"加载所有页面完成，共 {len(actual_pages)} 页")
        
        logger.info("✅ ODP内容加载完成")
        
    except Exception as e:
        logger.error(f"加载ODP内容失败: {e}", exc_info=True)
        # 清理临时ODP文件和临时目录
        if os.path.exists(odp_working_path):
            os.remove(odp_working_path)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None
    
    # ===== 第二步：翻译PPT内容 =====
    logger.info("=" * 60)
    logger.info("第2步：翻译PPT内容")
    logger.info("=" * 60)
    
    try:
        # 提取文本片段
        text_boxes_data, fragment_mapping = extract_texts_for_translation(ppt_data)
        
        if not text_boxes_data:
            logger.warning("没有找到需要翻译的文本框段落")
            # 即使没有翻译内容，也要返回原始文件
            logger.info("没有翻译内容，直接转换回PPTX")
        
        logger.info(f"提取到 {len(text_boxes_data)} 个需要翻译的文本框段落")
        
        # 调用翻译API
        from api_translate_uno import translate_pages_by_page, validate_translation_result
        translation_results = translate_pages_by_page(text_boxes_data, 
                                                      progress_callback, 
                                                      source_language, 
                                                      target_language, 
                                                      model,
                                                      stop_words_list,
                                                      custom_translations)
        
        logger.info(f"翻译完成，共处理 {len(translation_results)} 页")
        
        # 验证翻译结果
        validation_stats = validate_translation_result(translation_results, text_boxes_data)
        logger.info(f"翻译结果验证完成，覆盖率: {validation_stats['translation_coverage']:.2f}%")
        
        logger.info("✅ 翻译处理完成")
        
    except Exception as e:
        logger.error(f"翻译过程失败: {e}", exc_info=True)
        # 清理临时ODP文件和临时目录
        if os.path.exists(odp_working_path):
            os.remove(odp_working_path)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None
    
    # ===== 第三步：映射翻译结果 =====
    logger.info("=" * 60)
    logger.info("第3步：映射翻译结果回PPT数据结构")
    logger.info("=" * 60)
    
    try:
        translated_ppt_data = map_translation_results_back(ppt_data, translation_results, text_boxes_data)
        logger.info("✅ 翻译结果映射完成")
        
    except Exception as e:
        logger.error(f"映射翻译结果失败: {e}", exc_info=True)
        logger.info("映射失败，使用原始PPT数据")
        translated_ppt_data = ppt_data
    
    # ===== 第四步：将翻译结果写入PPTX（修改：使用python-pptx） =====
    logger.info("=" * 60)
    logger.info("第4步：将翻译结果写入PPTX（使用python-pptx）")
    logger.info("=" * 60)

    try:
        # 构建最终输出路径
        original_dir = os.path.dirname(presentation_path)
        original_name = os.path.splitext(os.path.basename(presentation_path))[0]
        output_path = os.path.join(original_dir, f"{original_name}_translated.pptx")
        
        # 调用新的PPTX编辑模块
        result_path = edit_ppt_with_pptx(
            backup_pptx_path, 
            translated_ppt_data, 
            bilingual_translation,
            validated_page_indices,  # 传入0-based索引
            output_path,
            progress_callback
        )
        
        logger.info(f"✅ 翻译内容写入PPTX成功: {result_path}")
        
    except Exception as e:
        logger.error(f"写入翻译结果到PPTX失败: {e}", exc_info=True)
        # 清理临时文件
        if os.path.exists(odp_working_path):
            os.remove(odp_working_path)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None
    
    # ===== 第五步：使用UNO接口进行格式转换（PPTX->ODP->PPTX） =====
    logger.info("=" * 60)
    logger.info("第5步：使用UNO接口进行格式转换（PPTX->ODP->PPTX）")
    logger.info("=" * 60)
    
    try:
        # 生成临时ODP文件路径
        temp_odp_name = f"{original_name}_temp_{timestamp}.odp"
        temp_odp_path = os.path.join(temp_dir, temp_odp_name)
        
        logger.info(f"开始PPTX转ODP转换: {result_path} -> {temp_odp_path}")
        
        # 使用UNO接口将翻译后的PPTX转换为ODP
        converted_odp_path = convert_pptx_to_odp_pyuno(result_path, temp_dir)
        
        if not converted_odp_path:
            logger.error("PPTX转ODP失败，将使用原始翻译结果")
            final_result_path = result_path
        else:
            # 重命名为临时ODP文件
            if converted_odp_path != temp_odp_path:
                os.rename(converted_odp_path, temp_odp_path)
                logger.info(f"重命名临时ODP文件: {temp_odp_path}")
            
            logger.info(f"✅ PPTX转ODP成功: {temp_odp_path}")
            
            # 使用UNO接口将ODP转换回PPTX
            logger.info(f"开始ODP转PPTX转换: {temp_odp_path} -> 最终PPTX")
            
            # 生成最终输出路径
            final_pptx_name = f"{original_name}_final_{timestamp}.pptx"
            final_result_path = os.path.join(original_dir, final_pptx_name)
            
            # 使用UNO接口将ODP转换为PPTX
            final_pptx_path = convert_odp_to_pptx_pyuno(temp_odp_path, original_dir)
            
            if not final_pptx_path:
                logger.error("ODP转PPTX失败，将使用中间翻译结果")
                final_result_path = result_path
            else:
                # 重命名为最终文件
                if final_pptx_path != final_result_path:
                    os.rename(final_pptx_path, final_result_path)
                    logger.info(f"重命名最终PPTX文件: {final_result_path}")
                
                logger.info(f"✅ ODP转PPTX成功: {final_result_path}")
                
                # 更新result_path为最终文件路径
                result_path = final_result_path
        
        logger.info(f"✅ UNO格式转换完成，最终文件: {final_result_path}")
        
    except Exception as e:
        logger.error(f"UNO格式转换失败: {e}", exc_info=True)
        logger.warning("格式转换失败，将使用原始翻译结果")
        final_result_path = result_path
    
    # ===== 处理完成统计 =====
    logger.info("=" * 60)
    logger.info("处理完成统计")
    logger.info("=" * 60)
    
    try:
        stats = ppt_data.get('statistics', {})
        total_pages = stats.get('total_pages', 0)
        total_boxes = stats.get('total_boxes', 0)
        total_paragraphs = stats.get('total_paragraphs', 0)
        total_fragments = stats.get('total_fragments', 0)
        
        successful_translations = 0
        total_translated_box_paragraphs = 0
        if 'translation_results' in locals():
            successful_translations = len([r for r in translation_results.values() if 'error' not in r])
            total_translated_box_paragraphs = sum(len(r.get('translated_fragments', {})) for r in translation_results.values())
        
        logger.info(f"处理完成统计:")
        logger.info(f"  - 总页数: {total_pages}")
        logger.info(f"  - 总文本框数: {total_boxes}")
        logger.info(f"  - 总段落数: {total_paragraphs}")
        logger.info(f"  - 总文本片段数: {total_fragments}")
        logger.info(f"  - 有内容的文本框段落数: {len(text_boxes_data) if 'text_boxes_data' in locals() else 0}")
        logger.info(f"  - 成功翻译页数: {successful_translations}")
        logger.info(f"  - 翻译文本框段落数: {total_translated_box_paragraphs}")
        logger.info(f"  - 中间翻译PPTX文件: {result_path}")
        if 'final_result_path' in locals() and final_result_path != result_path:
            logger.info(f"  - 最终PPTX文件: {final_result_path}")
            logger.info(f"  - 最终PPTX文件大小: {os.path.getsize(final_result_path) / (1024*1024):.2f} MB")
        else:
            logger.info(f"  - 最终PPTX文件: {result_path}")
            logger.info(f"  - PPTX文件大小: {os.path.getsize(result_path) / (1024*1024):.2f} MB")
        
        if select_page:
            logger.info(f"  - 请求处理页面: {select_page}")
            if 'actual_pages' in locals():
                logger.info(f"  - 实际处理页面数: {len(actual_pages)}")
        
        # 清理临时文件
        try:
            if os.path.exists(odp_working_path):
                os.remove(odp_working_path)
                logger.info(f"已删除临时ODP文件: {odp_working_path}")
            if 'temp_odp_path' in locals() and os.path.exists(temp_odp_path):
                os.remove(temp_odp_path)
                logger.info(f"已删除临时ODP文件: {temp_odp_path}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"已清理临时目录: {temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
        
        log_execution_time(logger, "pyuno_controller", start_time)
        
        logger.info("=" * 60)
        logger.info("🎉 pyuno_controller 处理完成！")
        logger.info("=" * 60)
        
        # 返回最终文件路径
        if 'final_result_path' in locals() and final_result_path != result_path:
            return final_result_path
        else:
            return result_path
        
    except Exception as e:
        logger.error(f"统计信息生成失败: {e}", exc_info=True)
        # 清理临时文件
        try:
            if os.path.exists(odp_working_path):
                os.remove(odp_working_path)
            if 'temp_odp_path' in locals() and os.path.exists(temp_odp_path):
                os.remove(temp_odp_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        # 返回最终文件路径
        if 'final_result_path' in locals() and final_result_path != result_path:
            return final_result_path
        else:
            return result_path if 'result_path' in locals() else None

def test_pyuno_format_conversion():
    """测试PyUNO格式转换功能"""
    logger = get_logger("pyuno.main")
    logger.info("=" * 60)
    logger.info("测试PyUNO格式转换功能")
    logger.info("=" * 60)
    
    test_pptx = "test.pptx"
    
    if not os.path.exists(test_pptx):
        logger.error(f"测试文件不存在: {test_pptx}")
        return False
    
    try:
        # 确保服务运行
        if not ensure_soffice_running():
            logger.error("LibreOffice服务启动失败")
            return False
        
        # 测试PPTX转ODP
        logger.info("测试PPTX转ODP...")
        odp_path = convert_pptx_to_odp_pyuno(test_pptx)
        if not odp_path:
            logger.error("PPTX转ODP失败")
            return False
        
        logger.info(f"✅ PPTX转ODP成功: {odp_path}")
        
        # 测试ODP转PPTX
        logger.info("测试ODP转PPTX...")
        final_pptx = convert_odp_to_pptx_pyuno(odp_path)
        if not final_pptx:
            logger.error("ODP转PPTX失败")
            return False
        
        logger.info(f"✅ ODP转PPTX成功: {final_pptx}")
        
        # 清理测试文件
        try:
            if os.path.exists(odp_path):
                os.remove(odp_path)
                logger.info(f"清理测试文件: {odp_path}")
        except:
            pass
        
        logger.info("✅ PyUNO格式转换测试通过！")
        return True
        
    except Exception as e:
        logger.error(f"格式转换测试失败: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("启动pyuno_controller（重构版 - PyUNO格式转换）")
    logger.info("=" * 60)
    
    # 首先测试格式转换功能
    logger.info("首先测试PyUNO格式转换功能...")
    if test_pyuno_format_conversion():
        logger.info("格式转换测试通过，开始完整流程测试...")
        
        try:
            result = pyuno_controller(
                presentation_path="test.pptx",
                stop_words_list=[],
                custom_translations={},
                select_page=[],
                source_language='en',
                target_language='zh',
                bilingual_translation='paragraph',
                progress_callback=None,
                model='qwen'
            )
            if result:
                logger.info(f"pyuno_controller执行成功: {result}")
            else:
                logger.error("pyuno_controller执行失败")
        except Exception as e:
            logger.error(f"pyuno_controller执行异常: {str(e)}", exc_info=True)
    else:
        logger.error("格式转换测试失败，跳过完整流程测试")