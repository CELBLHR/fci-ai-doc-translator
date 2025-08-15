"""
网络诊断工具
用于检查和诊断网络连接问题
"""
import socket
import time
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import subprocess
import platform

logger = logging.getLogger(__name__)

class NetworkDiagnostics:
    """网络诊断工具类"""
    
    def __init__(self):
        self.results = {}
    
    def check_dns_resolution(self, hostname: str) -> Tuple[bool, str]:
        """
        检查DNS解析
        
        Args:
            hostname: 主机名
            
        Returns:
            (是否成功, 结果信息)
        """
        try:
            ip_address = socket.gethostbyname(hostname)
            return True, f"DNS解析成功: {hostname} -> {ip_address}"
        except socket.gaierror as e:
            return False, f"DNS解析失败: {str(e)}"
    
    def check_tcp_connection(self, host: str, port: int, timeout: int = 10) -> Tuple[bool, str]:
        """
        检查TCP连接
        
        Args:
            host: 主机地址
            port: 端口号
            timeout: 超时时间
            
        Returns:
            (是否成功, 结果信息)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            start_time = time.time()
            result = sock.connect_ex((host, port))
            end_time = time.time()
            sock.close()
            
            if result == 0:
                return True, f"TCP连接成功: {host}:{port} (耗时: {end_time - start_time:.2f}秒)"
            else:
                return False, f"TCP连接失败: {host}:{port} (错误代码: {result})"
        except Exception as e:
            return False, f"TCP连接检查异常: {str(e)}"
    
    def ping_host(self, host: str, count: int = 4) -> Tuple[bool, str]:
        """
        Ping主机
        
        Args:
            host: 主机地址
            count: ping次数
            
        Returns:
            (是否成功, 结果信息)
        """
        try:
            # 根据操作系统选择ping命令
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", str(count), host]
            else:
                cmd = ["ping", "-c", str(count), host]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True, f"Ping成功:\n{result.stdout}"
            else:
                return False, f"Ping失败:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Ping超时"
        except Exception as e:
            return False, f"Ping异常: {str(e)}"
    
    async def check_http_connection(self, url: str, timeout: int = 30) -> Tuple[bool, str]:
        """
        检查HTTP连接
        
        Args:
            url: URL地址
            timeout: 超时时间
            
        Returns:
            (是否成功, 结果信息)
        """
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                start_time = time.time()
                async with session.get(url) as response:
                    end_time = time.time()
                    return True, f"HTTP连接成功: {url} (状态码: {response.status}, 耗时: {end_time - start_time:.2f}秒)"
        except asyncio.TimeoutError:
            return False, f"HTTP连接超时: {url}"
        except aiohttp.ClientError as e:
            return False, f"HTTP连接失败: {url} - {str(e)}"
        except Exception as e:
            return False, f"HTTP连接异常: {url} - {str(e)}"
    
    def check_proxy_settings(self) -> Dict[str, str]:
        """
        检查代理设置
        
        Returns:
            代理设置信息
        """
        import os
        proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
        proxy_settings = {}
        
        for var in proxy_vars:
            value = os.environ.get(var)
            if value:
                proxy_settings[var] = value
        
        return proxy_settings
    
    async def diagnose_api_connection(self, api_url: str) -> Dict[str, any]:
        """
        诊断API连接
        
        Args:
            api_url: API URL
            
        Returns:
            诊断结果
        """
        results = {
            'url': api_url,
            'timestamp': time.time(),
            'tests': {}
        }
        
        # 解析URL
        parsed_url = urlparse(api_url)
        hostname = parsed_url.hostname
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
        
        # 1. DNS解析检查
        dns_success, dns_msg = self.check_dns_resolution(hostname)
        results['tests']['dns'] = {'success': dns_success, 'message': dns_msg}
        
        # 2. TCP连接检查
        tcp_success, tcp_msg = self.check_tcp_connection(hostname, port)
        results['tests']['tcp'] = {'success': tcp_success, 'message': tcp_msg}
        
        # 3. Ping检查
        ping_success, ping_msg = self.ping_host(hostname)
        results['tests']['ping'] = {'success': ping_success, 'message': ping_msg}
        
        # 4. HTTP连接检查
        http_success, http_msg = await self.check_http_connection(api_url)
        results['tests']['http'] = {'success': http_success, 'message': http_msg}
        
        # 5. 代理设置检查
        proxy_settings = self.check_proxy_settings()
        results['proxy_settings'] = proxy_settings
        
        # 总体评估
        all_tests = [dns_success, tcp_success, ping_success, http_success]
        results['overall_success'] = any(all_tests)
        results['success_rate'] = sum(all_tests) / len(all_tests)
        
        return results
    
    def format_diagnosis_report(self, diagnosis: Dict[str, any]) -> str:
        """
        格式化诊断报告
        
        Args:
            diagnosis: 诊断结果
            
        Returns:
            格式化的报告
        """
        report = []
        report.append(f"=== 网络诊断报告 ===")
        report.append(f"URL: {diagnosis['url']}")
        report.append(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(diagnosis['timestamp']))}")
        report.append(f"总体成功率: {diagnosis['success_rate']:.1%}")
        report.append("")
        
        # 测试结果
        report.append("=== 测试结果 ===")
        for test_name, test_result in diagnosis['tests'].items():
            status = "✓" if test_result['success'] else "✗"
            report.append(f"{status} {test_name.upper()}: {test_result['message']}")
        
        # 代理设置
        if diagnosis['proxy_settings']:
            report.append("")
            report.append("=== 代理设置 ===")
            for var, value in diagnosis['proxy_settings'].items():
                report.append(f"{var}: {value}")
        else:
            report.append("")
            report.append("=== 代理设置 ===")
            report.append("未检测到代理设置")
        
        return "\n".join(report)

# 全局诊断实例
network_diagnostics = NetworkDiagnostics()

async def diagnose_network_issue(api_url: str) -> str:
    """
    诊断网络问题的便捷函数
    
    Args:
        api_url: API URL
        
    Returns:
        诊断报告
    """
    diagnosis = await network_diagnostics.diagnose_api_connection(api_url)
    return network_diagnostics.format_diagnosis_report(diagnosis)

def quick_connectivity_check(host: str, port: int = 443) -> bool:
    """
    快速连接性检查
    
    Args:
        host: 主机地址
        port: 端口号
        
    Returns:
        是否可以连接
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False
