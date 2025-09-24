import psutil
import GPUtil
from flask import current_app
from app.models import User
from app import db
import threading
import time

class SystemMonitor:
    def __init__(self):
        self._metrics = {
            'cpu': 0,
            'memory': 0,
            'gpu_memory': 0
        }
        self._lock = threading.Lock()
        self._app = None
        self._thread = None

    def start_monitoring(self, app=None):
        """启动后台监控线程"""
        if self._thread is not None:
            return
        
        if app is None:
            app = current_app._get_current_object()
        
        self._app = app
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def _monitor_loop(self):
        """持续监控系统指标"""
        while True:
            self._update_metrics()
            time.sleep(2)  # 每2秒更新一次

    def _update_metrics(self):
        """更新系统指标"""
        with self._lock:
            # CPU使用率
            self._metrics['cpu'] = psutil.cpu_percent()

            # 内存使用率
            memory = psutil.virtual_memory()
            self._metrics['memory'] = memory.percent

            # GPU内存使用
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    if gpu.memoryTotal > 0:
                        self._metrics['gpu_memory'] = (gpu.memoryUsed / gpu.memoryTotal) * 100  # 转换为百分比
                        # print(f"GPU Memory: Used={gpu.memoryUsed}MB, Total={gpu.memoryTotal}MB, Percentage={self._metrics['gpu_memory']}%")  # 调试信息
                    else:
                        self._metrics['gpu_memory'] = 0
                else:
                    self._metrics['gpu_memory'] = 0
            except Exception as e:
                print(f"Error getting GPU metrics: {e}")  # 调试信息
                self._metrics['gpu_memory'] = 0

    def get_metrics(self):
        """获取当前系统指标"""
        with self._lock:
            return self._metrics.copy()

# 创建全局监控实例
system_monitor = SystemMonitor() 