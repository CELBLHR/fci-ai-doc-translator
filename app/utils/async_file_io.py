"""
异步文件I/O工具类
提供异步文件读写操作，优化I/O性能
"""
import os
import aiofiles
import asyncio
from typing import Union, List, Dict, Any
import logging
import shutil
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import functools


# 配置日志记录器
logger = logging.getLogger(__name__)

# 为同步文件操作创建线程池
file_io_executor = ThreadPoolExecutor(
    max_workers=min(32, os.cpu_count() * 2),
    thread_name_prefix="async_file_io"
)

class AsyncFileIO:
    """异步文件I/O操作工具类"""
    
    @staticmethod
    async def read_file(file_path: str, mode: str = 'r', encoding: str = 'utf-8') -> str:
        """
        异步读取文件内容
        
        Args:
            file_path: 文件路径
            mode: 打开模式，默认为'r'（文本模式）
            encoding: 文件编码，默认为'utf-8'
            
        Returns:
            文件内容
        """
        try:
            async with aiofiles.open(file_path, mode=mode, encoding=encoding) as f:
                return await f.read()
        except Exception as e:
            logger.error(f"读取文件出错 {file_path}: {str(e)}")
            raise
    
    @staticmethod
    async def write_file(file_path: str, content: Union[str, bytes], mode: str = 'w', encoding: str = 'utf-8') -> None:
        """
        异步写入文件内容
        
        Args:
            file_path: 文件路径
            content: 文件内容（字符串或字节）
            mode: 打开模式，默认为'w'（文本写入模式）
            encoding: 文件编码，默认为'utf-8'
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        try:
            async with aiofiles.open(file_path, mode=mode, encoding=encoding if 'b' not in mode else None) as f:
                await f.write(content)
        except Exception as e:
            logger.error(f"写入文件出错 {file_path}: {str(e)}")
            raise
    
    @staticmethod
    async def append_file(file_path: str, content: str, encoding: str = 'utf-8') -> None:
        """
        异步追加内容到文件
        
        Args:
            file_path: 文件路径
            content: 要追加的内容
            encoding: 文件编码，默认为'utf-8'
        """
        await AsyncFileIO.write_file(file_path, content, mode='a', encoding=encoding)
    
    @staticmethod
    async def read_lines(file_path: str, encoding: str = 'utf-8') -> List[str]:
        """
        异步读取文件所有行
        
        Args:
            file_path: 文件路径
            encoding: 文件编码，默认为'utf-8'
            
        Returns:
            文件行列表
        """
        try:
            async with aiofiles.open(file_path, mode='r', encoding=encoding) as f:
                return await f.readlines()
        except Exception as e:
            logger.error(f"读取文件行出错 {file_path}: {str(e)}")
            raise
    
    @staticmethod
    async def read_chunks(file_path: str, chunk_size: int = 4096, mode: str = 'rb') -> bytes:
        """
        异步以数据块方式读取文件，适用于大文件
        
        Args:
            file_path: 文件路径
            chunk_size: 数据块大小，默认为4KB
            mode: 打开模式，默认为'rb'（二进制读取模式）
            
        Yields:
            数据块
        """
        try:
            async with aiofiles.open(file_path, mode=mode) as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            logger.error(f"分块读取文件出错 {file_path}: {str(e)}")
            raise
    
    @staticmethod
    async def file_exists(file_path: str) -> bool:
        """
        异步检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件是否存在
        """
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(file_io_executor, os.path.exists, file_path)
    
    @staticmethod
    async def get_file_size(file_path: str) -> int:
        """
        异步获取文件大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件大小（字节）
        """
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(file_io_executor, os.path.getsize, file_path)
    
    @staticmethod
    async def list_dir(dir_path: str) -> List[str]:
        """
        异步列出目录内容
        
        Args:
            dir_path: 目录路径
            
        Returns:
            目录内容列表
        """
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(file_io_executor, os.listdir, dir_path)
    
    @staticmethod
    async def mkdir(dir_path: str, exist_ok: bool = True) -> None:
        """
        异步创建目录
        
        Args:
            dir_path: 目录路径
            exist_ok: 如果为True，则目录已存在不会引发错误
        """
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            file_io_executor, 
            functools.partial(os.makedirs, dir_path, exist_ok=exist_ok)
        )
    
    @staticmethod
    async def remove_file(file_path: str) -> None:
        """
        异步删除文件
        
        Args:
            file_path: 文件路径
        """
        if await AsyncFileIO.file_exists(file_path):
            # 使用线程池执行同步操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(file_io_executor, os.remove, file_path)
    
    @staticmethod
    async def remove_dir(dir_path: str, recursive: bool = True) -> None:
        """
        异步删除目录
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归删除
        """
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        if recursive:
            await loop.run_in_executor(file_io_executor, shutil.rmtree, dir_path)
        else:
            await loop.run_in_executor(file_io_executor, os.rmdir, dir_path)
    
    @staticmethod
    async def copy_file(src_path: str, dst_path: str) -> None:
        """
        异步复制文件
        
        Args:
            src_path: 源文件路径
            dst_path: 目标文件路径
        """
        # 确保目标目录存在
        dst_dir = os.path.dirname(dst_path)
        if dst_dir:
            await AsyncFileIO.mkdir(dst_dir)
        
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(file_io_executor, shutil.copy2, src_path, dst_path)
    
    @staticmethod
    async def move_file(src_path: str, dst_path: str) -> None:
        """
        异步移动文件
        
        Args:
            src_path: 源文件路径
            dst_path: 目标文件路径
        """
        # 确保目标目录存在
        dst_dir = os.path.dirname(dst_path)
        if dst_dir:
            await AsyncFileIO.mkdir(dst_dir)
        
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(file_io_executor, shutil.move, src_path, dst_path)
    
    @staticmethod
    async def download_file(url: str, file_path: str, chunk_size: int = 8192,
                           headers: Dict[str, str] = None, timeout: int = 60) -> None:
        """
        异步下载文件
        
        Args:
            url: 下载URL
            file_path: 保存的文件路径
            chunk_size: 下载块大小，默认8KB
            headers: HTTP请求头
            timeout: 超时时间（秒）
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"下载文件失败，HTTP状态码: {response.status}")
                
                async with aiofiles.open(file_path, mode='wb') as f:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        await f.write(chunk)
    
    @staticmethod
    async def get_file_stats(file_path: str) -> Dict[str, Any]:
        """
        异步获取文件统计信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件统计信息字典
        """
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        stat_result = await loop.run_in_executor(file_io_executor, os.stat, file_path)
        
        return {
            'size': stat_result.st_size,
            'creation_time': stat_result.st_ctime,
            'modification_time': stat_result.st_mtime,
            'access_time': stat_result.st_atime
        }

# 创建函数别名，使API更简洁
async def read_file(file_path: str, mode: str = 'r', encoding: str = 'utf-8') -> str:
    """异步读取文件内容"""
    return await AsyncFileIO.read_file(file_path, mode, encoding)

async def write_file(file_path: str, content: Union[str, bytes], mode: str = 'w', encoding: str = 'utf-8') -> None:
    """异步写入文件内容"""
    await AsyncFileIO.write_file(file_path, content, mode, encoding)

async def list_dir(dir_path: str) -> List[str]:
    """异步列出目录内容"""
    return await AsyncFileIO.list_dir(dir_path)

async def file_exists(file_path: str) -> bool:
    """异步检查文件是否存在"""
    return await AsyncFileIO.file_exists(file_path)

async def get_file_size(file_path: str) -> int:
    """异步获取文件大小"""
    return await AsyncFileIO.get_file_size(file_path) 