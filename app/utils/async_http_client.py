"""
异步HTTP客户端
用于与API进行异步通信，支持超时、重试和并发请求
"""
import aiohttp
import asyncio
import logging

import time
from typing import Dict, Any, List, Optional, Union
from functools import wraps
import random
from aiohttp import ClientTimeout, TCPConnector


# 配置日志记录器
logger = logging.getLogger(__name__)

# 重试装饰器
def retry_async(max_retries=3, retry_delay=1.0, backoff_factor=2.0,
              exceptions=(aiohttp.ClientError, asyncio.TimeoutError)):
    """
    重试装饰器，用于异步函数

    Args:
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        backoff_factor: 退避因子，延迟时间将按此因子增长
        exceptions: 触发重试的异常类型元组
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            delay = retry_delay

            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"达到最大重试次数 {max_retries}，放弃重试: {str(e)}")
                        raise

                    # 添加随机抖动，避免多个请求同时重试
                    jitter = random.uniform(0.8, 1.2)
                    wait_time = delay * jitter

                    logger.warning(f"请求失败，将在 {wait_time:.2f} 秒后重试 ({retries}/{max_retries}): {str(e)}")
                    await asyncio.sleep(wait_time)

                    # 增加下次重试延迟
                    delay *= backoff_factor

        return wrapper

    return decorator

class AsyncHttpClient:
    """异步HTTP客户端，支持并发请求、重试和超时"""

    def __init__(self):
        """初始化 HTTP 客户端，但不创建会话，等待配置"""
        # 默认配置
        self.max_connections = 100
        self.default_timeout = 60  # 秒
        self.retry_times = 3
        self.retry_delay = 1  # 秒

        # 会话管理
        self._session: Optional[aiohttp.ClientSession] = None
        self.initialized = False

        # 统计信息
        self.request_count = 0
        self.error_count = 0
        self.retry_count = 0
        self.total_time = 0

        # 日志记录器
        self.logger = logging.getLogger(f"{__name__}.client")

    def configure(self, max_connections: Optional[int] = None,
                default_timeout: Optional[int] = None,
                retry_times: Optional[int] = None,
                retry_delay: Optional[int] = None) -> None:
        """
        配置 HTTP 客户端参数

        Args:
            max_connections: 最大并发连接数
            default_timeout: 默认超时时间（秒）
            retry_times: 重试次数
            retry_delay: 重试延迟（秒）
        """
        # 更新配置
        if max_connections is not None:
            self.max_connections = max_connections
        if default_timeout is not None:
            self.default_timeout = default_timeout
        if retry_times is not None:
            self.retry_times = retry_times
        if retry_delay is not None:
            self.retry_delay = retry_delay

        # 如果已经初始化，需要重新创建会话
        if self.initialized:
            self.close()

        # 标记为已配置，但不立即创建会话
        # 会话将在第一次使用时创建（当有事件循环时）
        self.initialized = True

        self.logger.info(
            f"HTTP 客户端已配置 - 最大连接数: {self.max_connections}, "
            f"超时: {self.default_timeout}秒, 重试次数: {self.retry_times}"
        )

    def _create_session(self) -> None:
        """创建新的 HTTP 会话"""
        if self._session:
            self.close()

        try:
            # 检查是否有运行的事件循环
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # 没有运行的事件循环，抛出异常
                # 会话创建应该在异步上下文中进行
                raise RuntimeError("无法在没有事件循环的环境中创建HTTP会话")

            # 创建连接器（新版本aiohttp不需要loop参数）
            connector = TCPConnector(
                limit=self.max_connections,
                force_close=True,
                enable_cleanup_closed=True
            )

            # 创建超时设置
            timeout = ClientTimeout(total=self.default_timeout)

            # 创建会话（新版本aiohttp不需要loop参数）
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                raise_for_status=True
            )

        except Exception as e:
            self.logger.error(f"创建HTTP会话失败: {str(e)}")
            # 如果创建失败，将在实际使用时重试
            self._session = None

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, str]] = None,
                timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        发送 GET 请求

        Args:
            url: 请求 URL
            params: URL 参数
            headers: 请求头
            timeout: 请求超时时间（秒）

        Returns:
            响应数据
        """
        return await self._request(
            "GET", url, params=params,
            headers=headers, timeout=timeout
        )

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None,
                 json: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        发送 POST 请求

        Args:
            url: 请求 URL
            data: 表单数据
            json: JSON 数据
            headers: 请求头
            timeout: 请求超时时间（秒）

        Returns:
            响应数据
        """
        return await self._request(
            "POST", url, data=data, json=json,
            headers=headers, timeout=timeout
        )

    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            method: 请求方法
            url: 请求 URL
            **kwargs: 其他请求参数

        Returns:
            响应数据
        """
        if not self.initialized:
            raise RuntimeError("HTTP 客户端未初始化")

        # 确保会话存在且有效
        if not self._session or self._session.closed:
            self._create_session()

        # 如果会话创建失败，抛出异常
        if not self._session:
            raise RuntimeError("无法创建HTTP会话，请检查事件循环配置")

        # 设置超时
        timeout = kwargs.pop('timeout', None)
        if timeout:
            kwargs['timeout'] = ClientTimeout(total=timeout)

        start_time = time.time()
        retries = 0
        last_error = None

        while retries <= self.retry_times:
            try:
                async with self._session.request(method, url, **kwargs) as response:
                    # 更新统计信息
                    self.request_count += 1
                    self.total_time += time.time() - start_time

                    # 返回 JSON 响应
                    return await response.json()

            except Exception as e:
                last_error = e
                retries += 1
                self.retry_count += 1

                if retries <= self.retry_times:
                    self.logger.warning(
                        f"请求失败，将重试 ({retries}/{self.retry_times}) - "
                        f"URL: {url}, 错误: {str(e)}"
                    )
                    await asyncio.sleep(self.retry_delay)
                else:
                    self.error_count += 1
                    self.logger.error(
                        f"请求失败，重试次数已达上限 - URL: {url}, 错误: {str(e)}"
                    )

        raise last_error

    def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._session and not self._session.closed:
            try:
                # 尝试获取当前事件循环
                try:
                    loop = asyncio.get_running_loop()
                    # 如果有运行的事件循环，创建任务来关闭会话
                    asyncio.create_task(self._session.close())
                except RuntimeError:
                    # 没有运行的事件循环，直接关闭连接器
                    if self._session._connector is not None:
                        self._session._connector.close()
            except Exception as e:
                self.logger.warning(f"关闭HTTP会话时出错: {str(e)}")
            finally:
                self._session = None

    def get_stats(self) -> Dict[str, Union[int, float]]:
        """
        获取客户端统计信息

        Returns:
            统计信息字典
        """
        return {
            'request_count': self.request_count,
            'error_count': self.error_count,
            'retry_count': self.retry_count,
            'average_time': self.total_time / (self.request_count or 1),
            'max_connections': self.max_connections,
            'default_timeout': self.default_timeout,
            'retry_times': self.retry_times,
            'retry_delay': self.retry_delay
        }

    async def health_check(self, urls: List[str]) -> Dict[str, bool]:
        """
        检查多个 URL 的健康状态

        Args:
            urls: URL 列表

        Returns:
            URL 健康状态字典
        """
        results = {}
        for url in urls:
            try:
                await self.get(url, timeout=5)
                results[url] = True
            except Exception as e:
                self.logger.warning(f"健康检查失败 - URL: {url}, 错误: {str(e)}")
                results[url] = False
        return results

# 创建全局 HTTP 客户端实例
http_client = AsyncHttpClient()

# 简化的API，不需要显式创建客户端
async def get(url: str, **kwargs) -> Dict[str, Any]:
    """异步GET请求简化API"""
    async with AsyncHttpClient() as client:
        return await client.get(url, **kwargs)

async def post(url: str, **kwargs) -> Dict[str, Any]:
    """异步POST请求简化API"""
    async with AsyncHttpClient() as client:
        return await client.post(url, **kwargs)