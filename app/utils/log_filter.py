#!/usr/bin/env python3
"""
日志过滤器模块
用于减少SQL查询和HTTP请求的日志噪音
"""
import os
import logging
import re
from typing import List, Optional


class SmartLogFilter(logging.Filter):
    """
    智能日志过滤器
    可以根据配置过滤不需要的日志消息
    """

    def __init__(self,
                 filter_sql: bool = True,
                 filter_http: bool = True,
                 filter_static: bool = True,
                 custom_patterns: Optional[List[str]] = None,
                 whitelist_patterns: Optional[List[str]] = None):
        """
        初始化过滤器

        Args:
            filter_sql: 是否过滤SQL查询日志
            filter_http: 是否过滤HTTP请求日志
            filter_static: 是否过滤静态资源请求
            custom_patterns: 自定义过滤模式列表
            whitelist_patterns: 白名单模式列表（匹配的日志不会被过滤）
        """
        super().__init__()
        self.filter_sql = filter_sql
        self.filter_http = filter_http
        self.filter_static = filter_static
        self.custom_patterns = custom_patterns or []
        self.whitelist_patterns = whitelist_patterns or []

        # 编译正则表达式以提高性能
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.sql_patterns = []
        self.http_patterns = []
        self.static_patterns = []
        self.custom_compiled = []
        self.whitelist_compiled = []

        if self.filter_sql:
            sql_raw_patterns = [
                # 基本SQL语句
                r'SELECT\s+.*FROM\s+\w+',
                r'INSERT\s+INTO\s+\w+',
                r'UPDATE\s+\w+\s+SET',
                r'DELETE\s+FROM\s+\w+',
                r'CREATE\s+TABLE\s+\w+',
                r'DROP\s+TABLE\s+\w+',
                r'ALTER\s+TABLE\s+\w+',

                # 事务控制
                r'ROLLBACK',
                r'COMMIT',
                r'BEGIN',
                r'START\s+TRANSACTION',

                # SQLAlchemy相关
                r'sqlalchemy\.engine',
                r'sqlalchemy\.pool',
                r'sqlalchemy\.orm',
                r'sqlalchemy\.dialects',

                # 数据库连接和操作
                r'WHERE\s+\w+\.\w+\s*[=<>!]',
                r'ORDER\s+BY\s+\w+\.\w+',
                r'GROUP\s+BY\s+\w+\.\w+',
                r'HAVING\s+\w+\.\w+',
                r'JOIN\s+\w+\s+ON',
                r'INNER\s+JOIN',
                r'LEFT\s+JOIN',
                r'RIGHT\s+JOIN',

                # 参数和绑定
                r'\{\'[\w_]+\':\s*[^}]+\}',  # 参数字典如 {'user_id_1': 1}
                r'%\([\w_]+\)s',  # SQLAlchemy参数占位符
                r'LIMIT\s+\d+',
                r'OFFSET\s+\d+',

                # 数据库特定操作
                r'PRAGMA\s+\w+',
                r'SHOW\s+\w+',
                r'DESCRIBE\s+\w+',
                r'EXPLAIN\s+',

                # 数据库连接信息
                r'mysql://',
                r'postgresql://',
                r'sqlite://',
                r'Database\s+connection',
                r'Connection\s+pool',

                # 表名和字段名模式
                r'\w+_records\.\w+',
                r'\w+_table\.\w+',
                r'AS\s+\w+_\w+',

                # 数据库日志特征
                r'Engine\s+\w+',
                r'Pool\s+\w+',
                r'Connection\s+\w+',
                r'Transaction\s+\w+'
            ]
            self.sql_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in sql_raw_patterns]

        if self.filter_http:
            http_raw_patterns = [
                r'127\.0\.0\.1\s+-\s+-\s+\[.*\]',
                r'GET\s+/\w+\s+HTTP/1\.1',
                r'POST\s+/\w+\s+HTTP/1\.1',
                r'HTTP/1\.1\s+\d+\s+-',
                r'"[A-Z]+\s+/[\w/]*\s+HTTP/1\.1"\s+\d+'
            ]
            self.http_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in http_raw_patterns]

        if self.filter_static:
            static_raw_patterns = [
                r'GET\s+/static/',
                r'GET\s+/favicon\.ico',
                r'GET\s+/css/',
                r'GET\s+/js/',
                r'GET\s+/images/',
                r'\.css\s+HTTP/1\.1',
                r'\.js\s+HTTP/1\.1',
                r'\.png\s+HTTP/1\.1',
                r'\.jpg\s+HTTP/1\.1',
                r'\.ico\s+HTTP/1\.1'
            ]
            self.static_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in static_raw_patterns]

        # 编译自定义模式
        for pattern in self.custom_patterns:
            try:
                self.custom_compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                # 如果不是正则表达式，当作普通字符串处理
                self.custom_compiled.append(pattern.lower())

        # 编译白名单模式
        for pattern in self.whitelist_patterns:
            try:
                self.whitelist_compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                self.whitelist_compiled.append(pattern.lower())

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录

        Args:
            record: 日志记录

        Returns:
            True表示保留日志，False表示过滤掉
        """
        try:
            message = record.getMessage()

            # 首先检查白名单
            if self._is_whitelisted(message):
                return True

            # 检查是否需要过滤
            if self._should_filter(message):
                return False

            return True

        except Exception:
            # 如果过滤过程出错，保留日志
            return True

    def _is_whitelisted(self, message: str) -> bool:
        """检查消息是否在白名单中"""
        for pattern in self.whitelist_compiled:
            if isinstance(pattern, re.Pattern):
                if pattern.search(message):
                    return True
            else:
                if pattern in message.lower():
                    return True
        return False

    def _should_filter(self, message: str) -> bool:
        """检查消息是否应该被过滤"""
        # 检查SQL模式
        if self.filter_sql:
            for pattern in self.sql_patterns:
                if pattern.search(message):
                    return True

        # 检查HTTP模式
        if self.filter_http:
            for pattern in self.http_patterns:
                if pattern.search(message):
                    return True

        # 检查静态资源模式
        if self.filter_static:
            for pattern in self.static_patterns:
                if pattern.search(message):
                    return True

        # 检查自定义模式
        for pattern in self.custom_compiled:
            if isinstance(pattern, re.Pattern):
                if pattern.search(message):
                    return True
            else:
                if pattern in message.lower():
                    return True

        return False


def configure_log_filtering():
    """
    配置日志过滤
    根据环境变量配置过滤器
    """
    # 从环境变量读取配置
    filter_sql = os.getenv('LOG_FILTER_SQL', 'true').lower() == 'true'
    filter_http = os.getenv('LOG_FILTER_HTTP', 'true').lower() == 'true'
    filter_static = os.getenv('LOG_FILTER_STATIC', 'true').lower() == 'true'

    # 自定义过滤模式
    custom_patterns_str = os.getenv('LOG_FILTER_CUSTOM_PATTERNS', '')
    custom_patterns = [p.strip() for p in custom_patterns_str.split(',') if p.strip()]

    # 白名单模式
    whitelist_patterns_str = os.getenv('LOG_FILTER_WHITELIST_PATTERNS', '')
    whitelist_patterns = [p.strip() for p in whitelist_patterns_str.split(',') if p.strip()]

    # 创建过滤器
    log_filter = SmartLogFilter(
        filter_sql=filter_sql,
        filter_http=filter_http,
        filter_static=filter_static,
        custom_patterns=custom_patterns,
        whitelist_patterns=whitelist_patterns
    )

    # 获取根日志记录器
    root_logger = logging.getLogger()

    # 为所有处理器添加过滤器
    for handler in root_logger.handlers:
        handler.addFilter(log_filter)

    # 配置特定日志记录器的级别 - 更严格的数据库日志过滤
    logger_configs = {
        # SQLAlchemy相关 - 完全静默数据库操作
        'sqlalchemy.engine': os.getenv('LOG_LEVEL_SQLALCHEMY', 'ERROR'),
        'sqlalchemy.engine.base': os.getenv('LOG_LEVEL_SQLALCHEMY_BASE', 'ERROR'),
        'sqlalchemy.engine.base.Engine': os.getenv('LOG_LEVEL_SQLALCHEMY_ENGINE', 'ERROR'),
        'sqlalchemy.pool': os.getenv('LOG_LEVEL_SQLALCHEMY_POOL', 'ERROR'),
        'sqlalchemy.pool.impl': os.getenv('LOG_LEVEL_SQLALCHEMY_POOL_IMPL', 'ERROR'),
        'sqlalchemy.pool.base': os.getenv('LOG_LEVEL_SQLALCHEMY_POOL_BASE', 'ERROR'),
        'sqlalchemy.orm': os.getenv('LOG_LEVEL_SQLALCHEMY_ORM', 'ERROR'),
        'sqlalchemy.dialects': os.getenv('LOG_LEVEL_SQLALCHEMY_DIALECTS', 'ERROR'),

        # HTTP服务器
        'werkzeug': os.getenv('LOG_LEVEL_WERKZEUG', 'WARNING'),

        # 网络请求
        'urllib3.connectionpool': os.getenv('LOG_LEVEL_URLLIB3', 'WARNING'),
        'requests.packages.urllib3': os.getenv('LOG_LEVEL_REQUESTS', 'WARNING'),
        'urllib3': os.getenv('LOG_LEVEL_URLLIB3_ROOT', 'WARNING'),

        # 数据库驱动
        'pymysql': os.getenv('LOG_LEVEL_PYMYSQL', 'ERROR'),
        'mysql.connector': os.getenv('LOG_LEVEL_MYSQL_CONNECTOR', 'ERROR'),
        'psycopg2': os.getenv('LOG_LEVEL_PSYCOPG2', 'ERROR'),
        'sqlite3': os.getenv('LOG_LEVEL_SQLITE3', 'ERROR'),
    }

    for logger_name, level_str in logger_configs.items():
        try:
            level = getattr(logging, level_str.upper())
            logging.getLogger(logger_name).setLevel(level)
        except AttributeError:
            # 如果级别名称无效，使用WARNING
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    # 记录过滤器配置
    app_logger = logging.getLogger('app')
    app_logger.info(f"日志过滤器已配置 - SQL:{filter_sql}, HTTP:{filter_http}, Static:{filter_static}")
    if custom_patterns:
        app_logger.info(f"自定义过滤模式: {custom_patterns}")
    if whitelist_patterns:
        app_logger.info(f"白名单模式: {whitelist_patterns}")


def create_development_filter():
    """
    创建开发环境专用的过滤器
    过滤更多的噪音日志
    """
    return SmartLogFilter(
        filter_sql=True,
        filter_http=True,
        filter_static=True,
        custom_patterns=[
            r'favicon\.ico',
            r'static/',
            r'css/',
            r'js/',
            r'images/',
            r'fonts/',
            r'HTTP/1\.1\s+304',  # 304 Not Modified
            r'HTTP/1\.1\s+200\s+-',  # 200 OK without content
        ],
        whitelist_patterns=[
            r'ERROR',
            r'WARNING',
            r'翻译',
            r'任务',
            r'上传',
            r'处理',
            r'失败',
            r'成功',
            r'开始',
            r'完成'
        ]
    )


def create_production_filter():
    """
    创建生产环境专用的过滤器
    只过滤最基本的噪音
    """
    return SmartLogFilter(
        filter_sql=False,  # 生产环境可能需要SQL日志用于调试
        filter_http=True,
        filter_static=True,
        custom_patterns=[
            r'favicon\.ico',
            r'HTTP/1\.1\s+304',
        ],
        whitelist_patterns=[
            r'ERROR',
            r'WARNING',
            r'CRITICAL'
        ]
    )


# 便捷函数
def apply_smart_filtering(environment: str = 'development'):
    """
    应用智能过滤

    Args:
        environment: 环境名称 ('development', 'production', 'custom')
    """
    if environment == 'development':
        log_filter = create_development_filter()
    elif environment == 'production':
        log_filter = create_production_filter()
    else:
        # 使用环境变量配置
        configure_log_filtering()
        return

    # 应用过滤器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(log_filter)

    # 配置特定日志记录器
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app_logger = logging.getLogger('app')
    app_logger.info(f"已应用 {environment} 环境的日志过滤器")
