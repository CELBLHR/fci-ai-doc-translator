"""
增强型线程池执行器
支持优先级任务、任务状态跟踪和异步I/O操作
"""
import threading
import queue
import time
import os
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto
from typing import Dict, Any, Callable, List, Optional, Union, TypeVar, Generic
import logging
import asyncio
from functools import partial
import traceback
import copy

# 任务类型定义
class TaskType(Enum):
    """任务类型枚举"""
    HIGH_PRIORITY = auto()
    IO_BOUND = auto()
    CPU_BOUND = auto()
    LOW_PRIORITY = auto()

# 任务状态定义
class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = 'pending'    # 等待执行
    RUNNING = 'running'    # 正在执行
    COMPLETED = 'completed'  # 已完成
    FAILED = 'failed'      # 执行失败
    CANCELED = 'canceled'  # 已取消

# 任务结果泛型类型
T = TypeVar('T')

class Task(Generic[T]):
    """任务对象，包含任务信息和执行状态"""
    
    def __init__(self, 
                func: Callable, 
                args: tuple = (), 
                kwargs: Dict[str, Any] = None,
                task_type: TaskType = TaskType.IO_BOUND,
                task_id: str = None,
                timeout: float = None,
                priority: int = 0,
                use_async_callback: bool = False):
        """
        初始化任务
        
        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            task_type: 任务类型，用于任务调度
            task_id: 任务唯一标识符
            timeout: 任务超时时间（秒）
            priority: 任务优先级（数字越小优先级越高）
            use_async_callback: 是否使用异步回调（避免线程自己加入自己）
        """
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.task_type = task_type
        self.task_id = task_id or f"task_{threading.get_ident()}_{int(time.time() * 1000)}"
        self.timeout = timeout
        self.priority = priority
        
        # 任务状态信息
        self.status = TaskStatus.PENDING
        self.result: Optional[T] = None
        self.error = None
        self.start_time = None
        self.end_time = None
        self.progress = 0
        
        # 回调函数
        self.callbacks = []
        
        # 用于任务取消的事件
        self.cancel_event = threading.Event()
        
        # 异步回调标志
        self.use_async_callback = use_async_callback
        
        # 记录执行任务的线程ID
        self.thread_id = None
    
    def should_cancel(self) -> bool:
        """检查任务是否应该取消"""
        return self.cancel_event.is_set()
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """添加任务完成后的回调函数"""
        self.callbacks.append(callback)
    
    def cancel(self) -> bool:
        """尝试取消任务，如果任务已经开始执行则返回False"""
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.CANCELED
            self.cancel_event.set()
            return True
        elif self.status == TaskStatus.RUNNING:
            # 仅设置取消标志，由执行函数决定是否中断
            self.cancel_event.set()
            return True
        return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        return {
            'task_id': self.task_id,
            'status': self.status.value,
            'progress': self.progress,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'error': str(self.error) if self.error else None,
            'task_type': self.task_type.name,
            'priority': self.priority
        }

class EnhancedThreadPoolExecutor:
    """增强型线程池执行器，支持优先级队列和异步操作"""
    
    def __init__(self):
        """初始化线程池，但不创建执行器，等待配置"""
        # 默认配置
        self.max_workers = min(32, os.cpu_count() * 2)
        self.io_bound_workers = int(self.max_workers * 0.75)
        self.cpu_bound_workers = os.cpu_count()
        self.thread_name_prefix = "worker"
        
        # 状态变量
        self.initialized = False
        self.running = False
        self.lock = threading.RLock()
        
        # 任务相关
        self.tasks: Dict[str, Task] = {}
        self.task_count = 0
        self.task_queues = {
            TaskType.HIGH_PRIORITY: queue.PriorityQueue(),
            TaskType.IO_BOUND: queue.PriorityQueue(),
            TaskType.CPU_BOUND: queue.PriorityQueue(),
            TaskType.LOW_PRIORITY: queue.PriorityQueue(),
        }
        
        # 监控指标
        self.last_error_time = 0
        self.error_count = 0
        self.last_recovery_time = 0
        self.recovery_count = 0
        self.executor_creation_time = 0
        
        # 日志记录器
        self.logger = logging.getLogger(__name__)
    
    def configure(self, max_workers: Optional[int] = None, 
                io_bound_workers: Optional[int] = None,
                cpu_bound_workers: Optional[int] = None,
                thread_name_prefix: Optional[str] = None) -> None:
        """
        配置线程池参数
        
        Args:
            max_workers: 最大工作线程数
            io_bound_workers: IO密集型任务线程数
            cpu_bound_workers: CPU密集型任务线程数
            thread_name_prefix: 线程名称前缀
        """
        with self.lock:
            # 更新配置
            if max_workers is not None:
                self.max_workers = max_workers
            if io_bound_workers is not None:
                self.io_bound_workers = io_bound_workers
            if cpu_bound_workers is not None:
                self.cpu_bound_workers = cpu_bound_workers
            if thread_name_prefix is not None:
                self.thread_name_prefix = thread_name_prefix
                
            # 如果已经初始化，需要先关闭现有的执行器
            if self.initialized:
                try:
                    self.logger.info("重新配置线程池，先关闭现有执行器")
                    self._shutdown_executors()
                except Exception as e:
                    self.logger.warning(f"关闭现有执行器时出错: {str(e)}")
                    # 继续初始化，不因关闭错误而中断
            
            # 标记为未初始化，以便重新创建
            self.initialized = False
            
            # 清空任务队列
            for task_type in TaskType:
                while not self.task_queues[task_type].empty():
                    try:
                        self.task_queues[task_type].get_nowait()
                    except:
                        pass
            
            # 创建新的执行器
            try:
                self._create_executors()
                self.initialized = True
                self.running = True
                self.executor_creation_time = time.time()
                self.logger.info(
                    f"线程池已配置 - IO线程: {self.io_bound_workers}, "
                    f"CPU线程: {self.cpu_bound_workers}"
                )
            except Exception as e:
                self.logger.error(f"创建执行器失败: {str(e)}")
                # 确保标记为未初始化
                self.initialized = False
                self.running = False
                raise
    
    def _create_executors(self) -> None:
        """创建线程池执行器"""
        try:
            self.logger.info("开始创建线程池执行器...")
            
            # 检查并关闭现有执行器
            if hasattr(self, 'io_executor') and self.io_executor:
                try:
                    if not getattr(self.io_executor, '_shutdown', False):
                        self.logger.debug("关闭现有IO执行器")
                        self.io_executor.shutdown(wait=False)
                except Exception as e:
                    self.logger.warning(f"关闭现有IO执行器时出错: {str(e)}")
            
            if hasattr(self, 'cpu_executor') and self.cpu_executor:
                try:
                    if not getattr(self.cpu_executor, '_shutdown', False):
                        self.logger.debug("关闭现有CPU执行器")
                        self.cpu_executor.shutdown(wait=False)
                except Exception as e:
                    self.logger.warning(f"关闭现有CPU执行器时出错: {str(e)}")
            
            # 创建IO执行器
            self.logger.debug(f"创建IO执行器，线程数: {self.io_bound_workers}")
            self.io_executor = ThreadPoolExecutor(
                max_workers=self.io_bound_workers,
                thread_name_prefix=f"{self.thread_name_prefix}_io"
            )
            
            # 创建CPU执行器
            self.logger.debug(f"创建CPU执行器，线程数: {self.cpu_bound_workers}")
            self.cpu_executor = ThreadPoolExecutor(
                max_workers=self.cpu_bound_workers,
                thread_name_prefix=f"{self.thread_name_prefix}_cpu"
            )
            
            # 设置运行状态和创建时间
            self.running = True
            self.executor_creation_time = time.time()
            
            # 检查现有调度线程
            if hasattr(self, 'scheduler_thread') and self.scheduler_thread and self.scheduler_thread.is_alive():
                self.logger.debug("检测到现有调度线程仍在运行，等待其结束")
                try:
                    # 尝试等待现有调度线程结束
                    self.scheduler_thread.join(timeout=2.0)
                    if self.scheduler_thread.is_alive():
                        self.logger.warning("现有调度线程未能在预期时间内结束")
                except Exception as e:
                    self.logger.warning(f"等待调度线程结束时出错: {str(e)}")
            
            # 启动新的调度线程
            self.logger.debug("创建并启动调度线程")
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name=f"{self.thread_name_prefix}_scheduler",
                daemon=True  # 设置为守护线程，确保主线程退出时它会自动终止
            )
            self.scheduler_thread.start()
            
            # 验证线程池是否正常创建
            if not hasattr(self, 'io_executor') or not hasattr(self, 'cpu_executor'):
                raise RuntimeError("线程池执行器创建失败")
            
            if not hasattr(self, 'scheduler_thread') or not self.scheduler_thread.is_alive():
                raise RuntimeError("调度线程创建失败")
            
            self.logger.info(
                f"线程池创建成功 - IO线程: {self.io_bound_workers}, "
                f"CPU线程: {self.cpu_bound_workers}, "
                f"调度线程ID: {self.scheduler_thread.ident}"
            )
        except Exception as e:
            self.logger.error(f"创建线程池执行器失败: {str(e)}")
            self.last_error_time = time.time()
            self.error_count += 1
            raise
    
    def _shutdown_executors(self) -> None:
        """
        关闭线程池执行器
        
        安全地关闭所有线程池和回调线程池
        """
        self.logger.info("正在关闭线程池执行器...")
        self.running = False
        
        # 获取当前线程ID，用于安全检查
        current_thread_id = threading.get_ident()
        
        # 关闭IO线程池
        if hasattr(self, 'io_executor'):
            try:
                self.logger.debug("正在关闭IO线程池...")
                # 检查是否在IO线程中执行关闭操作
                is_io_thread = False
                if hasattr(self.io_executor, '_threads'):
                    thread_ids = [t.ident for t in self.io_executor._threads if hasattr(t, 'ident') and t.ident]
                    if current_thread_id in thread_ids:
                        is_io_thread = True
                        self.logger.warning("尝试从IO线程中关闭线程池，这可能导致'cannot join current thread'错误，改为非阻塞关闭")
                
                # 如果是IO线程或者无法确定，使用非阻塞关闭
                if is_io_thread:
                    self.io_executor.shutdown(wait=False)
                else:
                    # 使用try-except包装，防止潜在的线程问题
                    try:
                        self.io_executor.shutdown(wait=True)
                    except RuntimeError as e:
                        if "cannot join current thread" in str(e):
                            self.logger.warning(f"检测到'cannot join current thread'错误，改为非阻塞关闭: {e}")
                            # 再次尝试非阻塞关闭
                            self.io_executor.shutdown(wait=False)
                        else:
                            raise
                
                self.logger.debug("IO线程池已关闭")
            except Exception as e:
                self.logger.error(f"关闭IO线程池时出错: {str(e)}")
        
        # 关闭CPU线程池
        if hasattr(self, 'cpu_executor'):
            try:
                self.logger.debug("正在关闭CPU线程池...")
                # 检查是否在CPU线程中执行关闭操作
                is_cpu_thread = False
                if hasattr(self.cpu_executor, '_threads'):
                    thread_ids = [t.ident for t in self.cpu_executor._threads if hasattr(t, 'ident') and t.ident]
                    if current_thread_id in thread_ids:
                        is_cpu_thread = True
                        self.logger.warning("尝试从CPU线程中关闭线程池，这可能导致'cannot join current thread'错误，改为非阻塞关闭")
                
                # 如果是CPU线程或者无法确定，使用非阻塞关闭
                if is_cpu_thread:
                    self.cpu_executor.shutdown(wait=False)
                else:
                    # 使用try-except包装，防止潜在的线程问题
                    try:
                        self.cpu_executor.shutdown(wait=True)
                    except RuntimeError as e:
                        if "cannot join current thread" in str(e):
                            self.logger.warning(f"检测到'cannot join current thread'错误，改为非阻塞关闭: {e}")
                            # 再次尝试非阻塞关闭
                            self.cpu_executor.shutdown(wait=False)
                        else:
                            raise
                
                self.logger.debug("CPU线程池已关闭")
            except Exception as e:
                self.logger.error(f"关闭CPU线程池时出错: {str(e)}")
        
        # 关闭回调线程池
        if hasattr(self, '_callback_executor'):
            try:
                self.logger.debug("正在关闭回调线程池...")
                # 回调线程池总是非阻塞关闭，避免阻塞
                self._callback_executor.shutdown(wait=False)
                self.logger.debug("回调线程池已关闭")
            except Exception as e:
                self.logger.error(f"关闭回调线程池时出错: {str(e)}")
        
        # 等待调度线程结束
        if hasattr(self, 'scheduler_thread') and self.scheduler_thread.is_alive():
            try:
                self.logger.debug("正在等待调度线程结束...")
                # 检查是否是调度线程自己
                if self.scheduler_thread.ident == current_thread_id:
                    self.logger.warning("尝试从调度线程中等待自己结束，这会导致死锁，跳过等待")
                else:
                    self.scheduler_thread.join(timeout=5.0)  # 最多等待5秒
                    if self.scheduler_thread.is_alive():
                        self.logger.warning("调度线程未在预期时间内结束")
                    else:
                        self.logger.debug("调度线程已结束")
            except Exception as e:
                self.logger.error(f"等待调度线程结束时出错: {str(e)}")
        
        self.logger.info("线程池执行器已关闭")
    
    def submit(self, func: Callable, args: tuple = (), 
              kwargs: Dict[str, Any] = None,
              task_type: TaskType = TaskType.IO_BOUND,
              priority: int = 0,
              task_id: str = None,
              timeout: float = None,
              use_async_callback: bool = False) -> Task:
        """
        提交任务到线程池
        
        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            task_type: 任务类型，用于任务调度
            priority: 任务优先级（数字越小优先级越高）
            task_id: 任务唯一标识符
            timeout: 任务超时时间（秒）
            use_async_callback: 是否使用异步回调（避免线程自己加入自己）
            
        Returns:
            任务对象
        """
        if not self.initialized:
            raise RuntimeError("线程池未初始化")
        
        with self.lock:
            # 创建任务对象
            task = Task(
                func=func,
                args=args,
                kwargs=kwargs,
                task_type=task_type,
                task_id=task_id,
                timeout=timeout,
                priority=priority,
                use_async_callback=use_async_callback
            )
            
            # 存储任务
            self.tasks[task.task_id] = task
            self.task_count += 1
            
            # 添加到任务队列
            self.task_queues[task_type].put((priority, task))
            
            # 记录任务提交信息
            self.logger.debug(
                f"任务已提交 - ID: {task.task_id}, 类型: {task_type.name}, "
                f"优先级: {priority}, 异步回调: {use_async_callback}"
            )
            
            return task
    
    def _scheduler_loop(self) -> None:
        """任务调度循环"""
        while self.running:
            try:
                # 按优先级顺序检查队列
                tasks_processed = False
                for task_type in TaskType:
                    try:
                        if not self.task_queues[task_type].empty():
                            # 获取任务
                            _, task = self.task_queues[task_type].get_nowait()
                            
                            # 检查任务是否已经被取消
                            if task.status == TaskStatus.CANCELED:
                                continue
                                
                            # 选择执行器
                            executor = (self.io_executor 
                                      if task.task_type in (TaskType.IO_BOUND, TaskType.HIGH_PRIORITY)
                                      else self.cpu_executor)
                            
                            # 提交任务到执行器
                            future = executor.submit(
                                self._execute_task,
                                task
                            )
                            
                            # 添加回调
                            future.add_done_callback(
                                lambda f, t=task: self._task_done_callback(f, t)
                            )
                            
                            tasks_processed = True
                            break
                    except Exception as e:
                        self.logger.error(f"处理队列 {task_type.name} 任务时出错: {str(e)}")
                        self.last_error_time = time.time()
                        self.error_count += 1
                
                # 如果没有处理任务，短暂休眠以避免CPU过度使用
                if not tasks_processed:
                    threading.Event().wait(0.01)
                
            except Exception as e:
                self.logger.error(f"调度器错误: {str(e)}")
                self.last_error_time = time.time()
                self.error_count += 1
                
                # 异常发生后短暂休眠，避免持续出错导致CPU使用率过高
                time.sleep(0.1)
                
                # 检查线程池是否需要重启
                try:
                    if (not hasattr(self, 'io_executor') or 
                        not hasattr(self, 'cpu_executor') or
                        self.io_executor._shutdown or 
                        self.cpu_executor._shutdown):
                        self.logger.warning("检测到线程池已关闭，尝试重新创建")
                        self._create_executors()
                except Exception as e2:
                    self.logger.error(f"重新创建线程池失败: {str(e2)}")
    
    def _execute_task(self, task: Task) -> Any:
        """
        执行任务
        
        安全地执行任务并处理异常，确保线程ID被正确记录
        实现超时处理和取消检查
        
        Args:
            task: 任务对象
            
        Returns:
            任务执行结果
        
        Raises:
            Exception: 任务执行过程中的异常会被重新抛出
        """
        # 记录当前线程ID
        task.thread_id = threading.get_ident()
        
        # 设置任务状态为运行中
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        
        self.logger.debug(
            f"开始执行任务 - ID: {task.task_id}, "
            f"线程ID: {task.thread_id}, "
            f"类型: {task.task_type.name}"
        )
        
        # 检查任务是否已被取消
        if task.cancel_event.is_set():
            task.status = TaskStatus.CANCELED
            self.logger.debug(f"任务已被取消，跳过执行: {task.task_id}")
            return None
        
        # 准备执行任务
        timer = None
        result = None
        
        try:
            # 确保kwargs已初始化
            if task.kwargs is None:
                task.kwargs = {}
            
            # 处理超时
            if task.timeout:
                # 创建定时器但不启动
                def timeout_handler():
                    # 检查线程安全
                    if threading.get_ident() == task.thread_id:
                        self.logger.error(f"超时处理器被调用在同一线程中，这可能导致死锁: {task.task_id}")
                        return
                    
                    if task.status == TaskStatus.RUNNING:
                        task.status = TaskStatus.FAILED
                        task.error = "任务执行超时"
                        task.cancel_event.set()
                        self.logger.warning(f"任务超时: {task.task_id}, 超时时间: {task.timeout}秒")
                
                # 创建并启动定时器
                timer = threading.Timer(task.timeout, timeout_handler)
                timer.daemon = True  # 设置为守护线程，避免阻止程序退出
                timer.start()
            
            # 检查函数是否可能导致线程自己加入自己
            if self._is_unsafe_function(task.func, task.thread_id):
                self.logger.warning(f"检测到可能导致线程自己加入自己的函数: {task.func}")
                task.use_async_callback = True  # 强制使用异步回调
            
            # 执行任务函数
            result = task.func(*task.args, **task.kwargs)
            
            # 记录任务执行时间
            task.execution_time = time.time() - task.start_time
            
            self.logger.debug(
                f"任务执行完成 - ID: {task.task_id}, "
                f"耗时: {task.execution_time:.2f}秒"
            )
            
            return result
            
        except Exception as e:
            # 记录错误信息
            error_message = str(e)
            task.error = error_message
            task.status = TaskStatus.FAILED
            
            # 特别处理线程自己加入自己的错误
            if "cannot join current thread" in error_message:
                self.logger.error(
                    f"任务执行异常: 检测到线程自己加入自己的错误 - "
                    f"任务ID: {task.task_id}, 线程ID: {task.thread_id}"
                )
                # 记录堆栈跟踪
                stack_trace = traceback.format_exc()
                self.logger.error(f"堆栈跟踪: {stack_trace}")
            else:
                self.logger.error(
                    f"任务执行异常 - 任务ID: {task.task_id}, "
                    f"错误: {error_message}"
                )
            
            # 更新错误统计
            self.last_error_time = time.time()
            self.error_count += 1
            
            # 重新抛出异常，让Future处理
            raise
        
        finally:
            # 取消定时器（如果存在）
            if timer:
                timer.cancel()
            
    def _is_unsafe_function(self, func, thread_id):
        """
        检查函数是否可能导致线程自己加入自己
        
        Args:
            func: 要检查的函数
            thread_id: 当前线程ID
            
        Returns:
            bool: 如果函数可能不安全返回True
        """
        # 检查函数是否是方法，如果是，检查它是否可能导致线程自己加入自己
        if hasattr(func, "__self__") and hasattr(func.__self__, "thread_id"):
            # 如果函数是一个方法，且其对象有thread_id属性
            if func.__self__.thread_id == thread_id:
                return True
                
        # 检查函数名称是否包含可能不安全的关键字
        func_name = func.__name__ if hasattr(func, "__name__") else str(func)
        unsafe_keywords = ["join", "wait", "lock", "event", "barrier", "semaphore"]
        
        for keyword in unsafe_keywords:
            if keyword.lower() in func_name.lower():
                # 可能不安全，但不一定
                return True
                
        return False
    
    def _task_done_callback(self, future, task: Task) -> None:
        """
        任务完成回调
        
        处理任务完成后的状态更新和回调执行
        确保线程安全，避免线程自己加入自己
        
        Args:
            future: Future对象
            task: 任务对象
        """
        try:
            # 记录当前线程ID和任务线程ID
            current_thread_id = threading.get_ident()
            task_thread_id = getattr(task, 'thread_id', None)
            
            # 记录调试信息
            self.logger.debug(
                f"任务完成回调开始 - 任务: {task.task_id}, "
                f"当前线程ID: {current_thread_id}, "
                f"任务线程ID: {task_thread_id}"
            )
            
            # 更新任务状态和结果
            try:
                # 获取任务结果
                result = future.result()
                task.result = result
                task.status = TaskStatus.COMPLETED
                self.logger.debug(f"任务成功完成: {task.task_id}")
            except concurrent.futures.CancelledError:
                # 任务被取消
                task.status = TaskStatus.CANCELED
                self.logger.debug(f"任务已取消: {task.task_id}")
            except Exception as e:
                # 任务执行失败
                task.error = str(e)
                task.status = TaskStatus.FAILED
                self.logger.error(f"任务执行失败: {task.task_id}, 错误: {str(e)}")
            finally:
                # 设置任务结束时间和取消事件
                task.end_time = time.time()
                task.cancel_event.set()
                
                # 更新任务计数和状态
                with self.lock:
                    # 更新计数
                    if task.status == TaskStatus.COMPLETED:
                        # 增加已完成任务计数
                        if hasattr(self, '_completed_tasks'):
                            self._completed_tasks += 1
                    elif task.status == TaskStatus.FAILED:
                        # 增加失败任务计数
                        self.error_count += 1
                        if hasattr(self, '_failed_tasks'):
                            self._failed_tasks += 1
                    elif task.status == TaskStatus.CANCELED:
                        # 增加取消任务计数
                        if hasattr(self, '_canceled_tasks'):
                            self._canceled_tasks += 1
                    
                    # 从活跃任务中移除（如果存在）
                    if hasattr(self, '_active_tasks') and task.task_id in self._active_tasks:
                        del self._active_tasks[task.task_id]
                    
                    # 标记任务已完成
                    if task.task_id in self.tasks:
                        self.tasks[task.task_id].is_done = True
                
                # 设置任务完成事件
                if hasattr(task, 'event') and task.event:
                    task.event.set()
            
            # 检查是否有回调函数
            if not task.callbacks:
                return
            
            # 确定回调执行方式
            use_async_callback = False
            
            # 以下情况使用异步回调:
            # 1. 明确设置了use_async_callback=True
            # 2. 当前线程是执行任务的线程
            if getattr(task, 'use_async_callback', False) or (task_thread_id and current_thread_id == task_thread_id):
                use_async_callback = True
                self.logger.debug(
                    f"使用异步回调 - 任务: {task.task_id}, "
                    f"原因: {'显式设置' if getattr(task, 'use_async_callback', False) else '当前线程是任务线程'}"
                )
            
            # 执行回调
            if use_async_callback:
                # 异步执行回调
                self._execute_callbacks_async(task)
            else:
                # 同步执行回调
                self._execute_callbacks_sync(task)
        
        except Exception as e:
            # 捕获所有异常，确保线程池不会因为回调错误而崩溃
            self.logger.error(
                f"任务回调处理异常 - 任务: {task.task_id}, "
                f"错误: {str(e)}\n{traceback.format_exc()}"
            )
    
    def _execute_callbacks_sync(self, task: Task) -> None:
        """
        同步执行回调函数
        
        Args:
            task: 任务对象
        """
        for callback in task.callbacks:
            try:
                callback(task)
            except Exception as e:
                self.logger.error(f"执行回调函数失败: {str(e)}")
    
    def _ensure_callback_executor(self) -> None:
        """
        确保回调线程池已创建
        
        如果回调线程池不存在或已关闭，则创建一个新的
        """
        with self.lock:
            if (not hasattr(self, '_callback_executor') or 
                self._callback_executor is None or 
                getattr(self._callback_executor, '_shutdown', False)):
                
                self.logger.info("创建回调线程池")
                self._callback_executor = ThreadPoolExecutor(
                    max_workers=5,  # 限制最大线程数
                    thread_name_prefix=f"{self.thread_name_prefix}_callback"
                )
                
    def _execute_callbacks_async(self, task: Task) -> None:
        """
        异步执行回调函数
        
        使用全局回调线程池执行回调，避免创建过多线程
        确保回调不会导致线程自己加入自己
        
        Args:
            task: 任务对象
        """
        # 确保有回调需要执行
        if not task.callbacks:
            return
        
        # 确保回调线程池存在
        self._ensure_callback_executor()
        
        # 记录当前线程ID和任务线程ID
        current_thread_id = threading.get_ident()
        task_thread_id = getattr(task, 'thread_id', None)
        
        # 记录调试信息
        self.logger.debug(
            f"准备异步执行回调 - 任务: {task.task_id}, "
            f"回调数量: {len(task.callbacks)}, "
            f"当前线程ID: {current_thread_id}, "
            f"任务线程ID: {task_thread_id}"
        )
        
        # 创建任务的副本，避免回调修改原始任务
        task_copy = copy.copy(task)
        
        # 定义安全的回调执行函数
        def safe_execute_callback(callback, task_obj):
            try:
                # 记录回调执行线程ID
                callback_thread_id = threading.get_ident()
                
                self.logger.debug(
                    f"执行回调 - 任务: {task_obj.task_id}, "
                    f"回调线程ID: {callback_thread_id}"
                )
                
                # 执行回调
                callback(task_obj)
                
            except Exception as e:
                # 记录错误但不传播异常
                self.logger.error(
                    f"回调执行失败 - 任务: {task_obj.task_id}, "
                    f"错误: {str(e)}\n{traceback.format_exc()}"
                )
        
        # 提交所有回调到线程池
        futures = []
        for callback in task.callbacks:
            try:
                # 检查回调是否安全
                if hasattr(callback, "__self__") and hasattr(callback.__self__, "thread_id"):
                    # 如果回调是一个方法，且其对象有thread_id属性
                    if callback.__self__.thread_id == current_thread_id:
                        self.logger.warning(f"跳过可能导致线程自加入的回调: {callback}")
                        continue
                
                # 提交回调到线程池
                future = self._callback_executor.submit(safe_execute_callback, callback, task_copy)
                futures.append(future)
                
            except Exception as e:
                self.logger.error(
                    f"提交回调失败 - 任务: {task.task_id}, "
                    f"错误: {str(e)}"
                )
        
        # 不等待futures完成，让它们在后台执行
        self.logger.debug(f"已提交 {len(futures)} 个回调到线程池 - 任务: {task.task_id}")
    
    def _task_timeout(self, task: Task) -> None:
        """
        任务超时处理
        
        Args:
            task: 任务对象
        """
        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.FAILED
            task.error = "任务执行超时"
            task.cancel_event.set()
    
    def shutdown(self, wait: bool = True) -> None:
        """
        关闭线程池
        
        Args:
            wait: 是否等待所有任务完成
        """
        with self.lock:
            if not self.initialized:
                return
            
            # 使用安全关闭机制
            self.safe_shutdown(wait=wait, timeout=10.0)
            
            # 确保标记为未初始化
            self.initialized = False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取线程池统计信息
        
        Returns:
            统计信息字典
        """
        with self.lock:
            # 统计不同状态的任务数量
            status_counts = {status.value: 0 for status in TaskStatus}
            for task in self.tasks.values():
                status_counts[task.status.value] += 1
            
            # 线程池运行时间
            uptime = 0
            if self.executor_creation_time > 0:
                uptime = time.time() - self.executor_creation_time
            
            return {
                'max_workers': self.max_workers,
                'io_bound_workers': self.io_bound_workers,
                'cpu_bound_workers': self.cpu_bound_workers,
                'task_status_counts': status_counts,
                'total_tasks_created': self.task_count,
                'active_tasks': len(self.tasks),
                'error_count': self.error_count,
                'recovery_count': self.recovery_count,
                'last_error_time': self.last_error_time,
                'last_recovery_time': self.last_recovery_time,
                'uptime': uptime,
                'io_active_threads': self.get_io_active_count(),
                'cpu_active_threads': self.get_cpu_active_count()
            }
            
    def get_io_active_count(self) -> int:
        """
        获取当前活动的IO线程数量
        
        Returns:
            活动IO线程数量
        """
        if hasattr(self, 'io_executor') and self.io_executor:
            return len(self.io_executor._threads)
        return 0
        
    def get_cpu_active_count(self) -> int:
        """
        获取当前活动的CPU线程数量
        
        Returns:
            活动CPU线程数量
        """
        if hasattr(self, 'cpu_executor') and self.cpu_executor:
            return len(self.cpu_executor._threads)
        return 0
        
    def get_task_count(self) -> int:
        """
        获取总任务数
        
        Returns:
            总任务数
        """
        return self.task_count
        
    def get_completed_task_count(self) -> int:
        """
        获取已完成任务数
        
        Returns:
            已完成任务数
        """
        with self.lock:
            return sum(1 for task in self.tasks.values() if task.status == TaskStatus.COMPLETED)

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取线程池健康状态
        
        Returns:
            健康状态信息字典
        """
        try:
            io_active = self.get_io_active_count()
            cpu_active = self.get_cpu_active_count()
            
            # 判断是否健康
            # 修改健康判断逻辑：不再要求IO线程必须活跃，只要线程池已初始化且运行中即可
            is_healthy = (
                self.initialized and 
                self.running and
                hasattr(self, 'io_executor') and 
                hasattr(self, 'cpu_executor') and
                not getattr(self.io_executor, '_shutdown', False) and
                not getattr(self.cpu_executor, '_shutdown', False) and
                hasattr(self, 'scheduler_thread') and 
                self.scheduler_thread.is_alive()
            )
            
            health_status = {
                'healthy': is_healthy,
                'initialized': self.initialized,
                'running': self.running,
                'io_executor_alive': hasattr(self, 'io_executor') and not getattr(self.io_executor, '_shutdown', False),
                'cpu_executor_alive': hasattr(self, 'cpu_executor') and not getattr(self.cpu_executor, '_shutdown', False),
                'io_active_threads': io_active,
                'cpu_active_threads': cpu_active,
                'scheduler_thread_alive': hasattr(self, 'scheduler_thread') and self.scheduler_thread.is_alive(),
                'uptime': time.time() - self.executor_creation_time if self.executor_creation_time > 0 else 0,
                'last_error': self.last_error_time,
                'error_count': self.error_count
            }
            
            # 添加更详细的诊断信息
            if not is_healthy:
                health_status['diagnosis'] = []
                if not self.initialized:
                    health_status['diagnosis'].append("线程池未初始化")
                if not self.running:
                    health_status['diagnosis'].append("线程池未运行")
                if not hasattr(self, 'io_executor'):
                    health_status['diagnosis'].append("IO执行器不存在")
                elif getattr(self.io_executor, '_shutdown', False):
                    health_status['diagnosis'].append("IO执行器已关闭")
                if not hasattr(self, 'cpu_executor'):
                    health_status['diagnosis'].append("CPU执行器不存在")
                elif getattr(self.cpu_executor, '_shutdown', False):
                    health_status['diagnosis'].append("CPU执行器已关闭")
                if not hasattr(self, 'scheduler_thread'):
                    health_status['diagnosis'].append("调度线程不存在")
                elif not self.scheduler_thread.is_alive():
                    health_status['diagnosis'].append("调度线程未运行")
            
            return health_status
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'diagnosis': ["获取健康状态时发生异常"]
            }

    def safe_shutdown(self, wait: bool = False, timeout: float = 5.0) -> None:
        """
        安全关闭线程池，可以在任何线程中调用
        
        使用专用的关闭线程来避免"cannot join current thread"错误
        
        Args:
            wait: 是否等待关闭完成
            timeout: 等待超时时间（秒）
        """
        # 获取当前线程ID，用于安全检查
        current_thread_id = threading.get_ident()
        
        # 检查是否已经在关闭中或未初始化
        if not self.running:
            self.logger.info("线程池已经关闭，无需再次关闭")
            return
            
        # 如果未初始化，则标记为已初始化，然后继续关闭流程
        if not self.initialized:
            self.logger.info("线程池未初始化，但仍将执行关闭流程")
            self.initialized = True  # 临时标记为已初始化，以便执行关闭逻辑
            
        self.logger.info("安全关闭线程池...")
        
        # 检查是否在线程池的线程中执行关闭操作
        is_pool_thread = False
        
        # 检查IO线程池
        if hasattr(self, 'io_executor') and hasattr(self.io_executor, '_threads'):
            thread_ids = [t.ident for t in self.io_executor._threads if t.ident]
            if current_thread_id in thread_ids:
                is_pool_thread = True
                self.logger.warning("从IO线程中调用关闭，将使用安全关闭机制")
                
        # 检查CPU线程池
        if not is_pool_thread and hasattr(self, 'cpu_executor') and hasattr(self.cpu_executor, '_threads'):
            thread_ids = [t.ident for t in self.cpu_executor._threads if t.ident]
            if current_thread_id in thread_ids:
                is_pool_thread = True
                self.logger.warning("从CPU线程中调用关闭，将使用安全关闭机制")
                
        # 检查回调线程池
        if not is_pool_thread and hasattr(self, '_callback_executor') and hasattr(self._callback_executor, '_threads'):
            thread_ids = [t.ident for t in self._callback_executor._threads if t.ident]
            if current_thread_id in thread_ids:
                is_pool_thread = True
                self.logger.warning("从回调线程中调用关闭，将使用安全关闭机制")
                
        # 检查调度线程
        if not is_pool_thread and hasattr(self, 'scheduler_thread') and self.scheduler_thread.ident == current_thread_id:
            is_pool_thread = True
            self.logger.warning("从调度线程中调用关闭，将使用安全关闭机制")
            
        # 如果是在线程池的线程中调用，使用专用线程关闭
        if is_pool_thread:
            # 标记为正在关闭
            self.running = False
            
            # 创建关闭事件
            shutdown_event = threading.Event()
            
            # 创建关闭线程
            shutdown_thread = threading.Thread(
                target=self._shutdown_worker,
                name="thread_pool_shutdown",
                args=(shutdown_event,)
            )
            
            # 启动关闭线程
            shutdown_thread.start()
            
            # 如果需要等待关闭完成
            if wait:
                shutdown_event.wait(timeout)
                if not shutdown_event.is_set():
                    self.logger.warning(f"等待线程池关闭超时（{timeout}秒）")
        else:
            # 直接关闭
            self._shutdown_executors()
            self.initialized = False
            
    def _shutdown_worker(self, shutdown_event: threading.Event) -> None:
        """
        在专用线程中执行关闭操作
        
        Args:
            shutdown_event: 关闭完成事件
        """
        try:
            self.logger.info("在专用线程中执行线程池关闭")
            self._shutdown_executors()
            self.initialized = False
            self.logger.info("线程池已在专用线程中安全关闭")
        except Exception as e:
            self.logger.error(f"在专用线程中关闭线程池时出错: {str(e)}")
        finally:
            # 设置关闭完成事件
            shutdown_event.set()

# 创建全局线程池执行器实例
thread_pool = EnhancedThreadPoolExecutor() 