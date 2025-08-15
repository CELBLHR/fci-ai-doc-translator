"""
懒加载HTTP客户端
解决在Flask应用初始化时创建aiohttp会话的事件循环问题
"""
import asyncio
import logging
from typing import Dict, Any, Optional
import aiohttp
from aiohttp import ClientTimeout, TCPConnector


class LazyAsyncHttpClient:
    """懒加载异步HTTP客户端，只在实际使用时创建会话"""
    
    def __init__(self):
        """初始化客户端，但不创建会话"""
        # 配置参数
        self.max_connections = 100
        self.default_timeout = 60
        self.retry_times = 3
        self.retry_delay = 1
        
        # 会话管理
        self._session: Optional[aiohttp.ClientSession] = None
        self.configured = False
        
        # 日志记录器
        self.logger = logging.getLogger(f"{__name__}.lazy_client")
    
    def configure(self, max_connections: Optional[int] = None,
                 default_timeout: Optional[int] = None,
                 retry_times: Optional[int] = None,
                 retry_delay: Optional[int] = None) -> None:
        """
        配置HTTP客户端参数
        
        Args:
            max_connections: 最大并发连接数
            default_timeout: 默认超时时间（秒）
            retry_times: 重试次数
            retry_delay: 重试延迟（秒）
        """
        if max_connections is not None:
            self.max_connections = max_connections
        if default_timeout is not None:
            self.default_timeout = default_timeout
        if retry_times is not None:
            self.retry_times = retry_times
        if retry_delay is not None:
            self.retry_delay = retry_delay
        
        self.configured = True
        
        self.logger.info(
            f"懒加载HTTP客户端已配置 - 最大连接数: {self.max_connections}, "
            f"超时: {self.default_timeout}秒, 重试次数: {self.retry_times}"
        )
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """确保会话存在，如果不存在则创建"""
        if not self.configured:
            raise RuntimeError("HTTP客户端未配置，请先调用configure()方法")
        
        if self._session is None or self._session.closed:
            # 创建连接器
            connector = TCPConnector(
                limit=self.max_connections,
                force_close=True,
                enable_cleanup_closed=True
            )
            
            # 创建超时设置
            timeout = ClientTimeout(total=self.default_timeout)
            
            # 创建会话
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                raise_for_status=True
            )
            
            self.logger.debug("HTTP会话已创建")
        
        return self._session
    
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            params: URL参数
            headers: 请求头
            timeout: 请求超时时间（秒）
            
        Returns:
            响应数据
        """
        session = await self._ensure_session()
        
        # 设置超时
        request_timeout = ClientTimeout(total=timeout) if timeout else None
        
        async with session.get(url, params=params, headers=headers, timeout=request_timeout) as response:
            return await response.json()
    
    async def post(self, url: str, data: Optional[Dict[str, Any]] = None,
                  json: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None,
                  timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        发送POST请求
        
        Args:
            url: 请求URL
            data: 表单数据
            json: JSON数据
            headers: 请求头
            timeout: 请求超时时间（秒）
            
        Returns:
            响应数据
        """
        session = await self._ensure_session()
        
        # 设置超时
        request_timeout = ClientTimeout(total=timeout) if timeout else None
        
        async with session.post(url, data=data, json=json, headers=headers, timeout=request_timeout) as response:
            return await response.json()
    
    async def close(self) -> None:
        """关闭HTTP客户端"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self.logger.debug("HTTP会话已关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 创建全局懒加载HTTP客户端实例
lazy_http_client = LazyAsyncHttpClient()


# 兼容性包装器，保持与原有代码的兼容性
class CompatibleAsyncHttpClient:
    """兼容性HTTP客户端，包装懒加载客户端"""
    
    def __init__(self):
        self.lazy_client = lazy_http_client
        self.initialized = False
    
    def configure(self, max_connections: Optional[int] = None,
                 default_timeout: Optional[int] = None,
                 retry_times: Optional[int] = None,
                 retry_delay: Optional[int] = None) -> None:
        """配置HTTP客户端（同步方法，不会创建会话）"""
        self.lazy_client.configure(
            max_connections=max_connections,
            default_timeout=default_timeout,
            retry_times=retry_times,
            retry_delay=retry_delay
        )
        self.initialized = True
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """发送GET请求"""
        return await self.lazy_client.get(url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """发送POST请求"""
        return await self.lazy_client.post(url, **kwargs)
    
    def close(self) -> None:
        """关闭HTTP客户端（同步方法）"""
        # 在同步环境中，我们不能直接调用异步方法
        # 这里只是标记需要关闭，实际关闭会在下次使用时处理
        if self.lazy_client._session:
            try:
                # 尝试获取事件循环
                loop = asyncio.get_running_loop()
                # 如果有运行的事件循环，创建任务来关闭会话
                asyncio.create_task(self.lazy_client.close())
            except RuntimeError:
                # 没有运行的事件循环，标记会话为需要重新创建
                if self.lazy_client._session and not self.lazy_client._session.closed:
                    # 直接关闭连接器
                    if hasattr(self.lazy_client._session, '_connector') and self.lazy_client._session._connector:
                        self.lazy_client._session._connector.close()
                self.lazy_client._session = None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'configured': self.lazy_client.configured,
            'session_exists': self.lazy_client._session is not None,
            'max_connections': self.lazy_client.max_connections,
            'default_timeout': self.lazy_client.default_timeout,
            'retry_times': self.lazy_client.retry_times,
            'retry_delay': self.lazy_client.retry_delay
        }


# 创建兼容的HTTP客户端实例
http_client = CompatibleAsyncHttpClient()
