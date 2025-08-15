from collections import deque
from threading import Lock
import time
from datetime import datetime


class TranslationQueue:
    def __init__(self):
        self.queue = deque()  # 存储任务的队列
        self.lock = Lock()  # 线程锁
        self.current_task = None  # 当前正在执行的任务
        self.completed_tasks = {}  # 存储已完成的任务
        self.max_queue_size = 10  # 最大队列长度限制

    def add_task(self, user_id, user_name, file_path, annotation_filename,select_page,source_language, target_language,bilingual_translation):
        """添加新的翻译任务到队列"""
        with self.lock:
            # 检查队列长度限制
            total_tasks = len(self.queue) + (1 if self.current_task else 0)
            if total_tasks >= self.max_queue_size:
                raise RuntimeError(f"翻译任务队列已满，当前有 {total_tasks} 个任务，最大限制为 {self.max_queue_size} 个")

            task = {
                'user_id': user_id,
                'user_name': user_name,
                'file_path': file_path,
                'annotation_filename': annotation_filename,
                'status': 'waiting',  # waiting, processing, completed, failed
                'position': len(self.queue) + 1,
                'created_at': datetime.now(),
                'started_at': None,
                'completed_at': None,
                'select_page':select_page,
                'error': None,
                'current_slide': 0,  # 当前正在翻译的幻灯片编号
                'total_slides': 0,  # 幻灯片总数
                'progress': 0  ,# 翻译进度（百分比）
                "source_language": source_language,
                "target_language": target_language,
                'bilingual_translation':bilingual_translation
            }
            self.queue.append(task)
            # 更新所有等待中任务的位置
            self._update_queue_positions()
            return len(self.queue)  # 返回队列位置

    def get_task_status(self, user_id):
        """获取指定用户的任务状态"""
        with self.lock:
            # 检查当前正在执行的任务
            if self.current_task and self.current_task['user_id'] == user_id:
                return {
                    'status': self.current_task['status'],
                    'position': 0,
                    'started_at': self.current_task['started_at'],
                    'current_slide': self.current_task['current_slide'],
                    'total_slides': self.current_task['total_slides'],
                    'progress': self.current_task['progress']
                }

            # 检查队列中的任务
            for i, task in enumerate(self.queue):
                if task['user_id'] == user_id:
                    return {
                        'status': task['status'],
                        'position': i + 1,
                        'created_at': task['created_at'],
                        'current_slide': task['current_slide'],
                        'total_slides': task['total_slides'],
                        'progress': task['progress']
                    }

            # 检查已完成的任务
            if user_id in self.completed_tasks:
                task = self.completed_tasks[user_id]
                # 如果任务完成超过5分钟，删除记录
                if (datetime.now() - task['completed_at']).total_seconds() > 300:
                    del self.completed_tasks[user_id]
                    return None
                return {
                    'status': task['status'],
                    'completed_at': task['completed_at'],
                    'error': task['error'],
                    'current_slide': task['current_slide'],
                    'total_slides': task['total_slides'],
                    'progress': task['progress']
                }

            return None

    def start_next_task(self):
        """开始执行队列中的下一个任务"""
        with self.lock:
            if not self.queue or self.current_task:
                return None

            self.current_task = self.queue.popleft()
            self.current_task['status'] = 'processing'
            self.current_task['started_at'] = datetime.now()
            # 更新所有等待中任务的位置
            self._update_queue_positions()
            return self.current_task

    def complete_current_task(self, success=True, error=None):
        """完成当前任务"""
        with self.lock:
            if not self.current_task:
                return

            self.current_task['status'] = 'completed' if success else 'failed'
            self.current_task['completed_at'] = datetime.now()
            self.current_task['error'] = error

            # 将完成的任务存储到已完成任务字典中
            self.completed_tasks[self.current_task['user_id']] = self.current_task
            self.current_task = None

            # 更新所有等待中任务的位置
            self._update_queue_positions()

    def update_progress(self, current_slide, total_slides):
        """更新当前任务的翻译进度"""
        with self.lock:
            if not self.current_task:
                return

            self.current_task['current_slide'] = current_slide
            self.current_task['total_slides'] = total_slides
            self.current_task['progress'] = int((current_slide / total_slides) * 100)

    def _update_queue_positions(self):
        """更新队列中所有任务的位置"""
        for i, task in enumerate(self.queue):
            task['position'] = i + 1


# 创建全局队列实例
translation_queue = TranslationQueue()
