#!/usr/bin/env python3
"""
数据库迁移脚本：修改 translation 表结构

此脚本将添加以下列到 translation 表：
- dutch (VARCHAR(500), 可为空)
- class1 (VARCHAR(500), 可为空)
- class2 (VARCHAR(500), 可为空)
- is_public (TINYINT(1), 默认值 0, 不可为空)

同时确保 user_id 列可以为空，并设置表的字符集为 utf8mb4。
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# 将项目根目录添加到 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from app.config import Config

def column_exists(connection, table_name, column_name):
    """
    检查指定表中是否存在指定列
    
    Args:
        connection: 数据库连接
        table_name: 表名
        column_name: 列名
    
    Returns:
        bool: 如果列存在返回True，否则返回False
    """
    result = connection.execute(
        text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = :table_name
            AND COLUMN_NAME = :column_name
        """),
        {"table_name": table_name, "column_name": column_name}
    )
    return result.scalar() > 0

def migrate_translation_table():
    """
    执行 translation 表的迁移
    """
    # 获取数据库连接 URL
    db_url = f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
    
    try:
        # 创建数据库引擎
        engine = create_engine(db_url)
        
        # 连接到数据库
        with engine.connect() as connection:
            # 开始事务
            trans = connection.begin()
            
            try:
                print("开始迁移 translation 表...")
                
                # 检查并添加 dutch 列
                if not column_exists(connection, "translation", "dutch"):
                    connection.execute(text("""
                        ALTER TABLE translation 
                        ADD COLUMN dutch VARCHAR(500) NULL
                    """))
                    print("已添加 dutch 列")
                else:
                    print("dutch 列已存在，跳过")
                
                # 检查并添加 class1 列
                if not column_exists(connection, "translation", "class1"):
                    connection.execute(text("""
                        ALTER TABLE translation 
                        ADD COLUMN class1 VARCHAR(500) NULL
                    """))
                    print("已添加 class1 列")
                else:
                    print("class1 列已存在，跳过")
                
                # 检查并添加 class2 列
                if not column_exists(connection, "translation", "class2"):
                    connection.execute(text("""
                        ALTER TABLE translation 
                        ADD COLUMN class2 VARCHAR(500) NULL
                    """))
                    print("已添加 class2 列")
                else:
                    print("class2 列已存在，跳过")
                
                # 检查并添加 is_public 列
                if not column_exists(connection, "translation", "is_public"):
                    connection.execute(text("""
                        ALTER TABLE translation 
                        ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0
                    """))
                    print("已添加 is_public 列")
                else:
                    print("is_public 列已存在，跳过")
                
                # 修改 user_id 列使其可为空
                connection.execute(text("""
                    ALTER TABLE translation 
                    MODIFY COLUMN user_id INT NULL
                """))
                print("已修改 user_id 列为可为空")
                
                # 设置表的字符集和排序规则
                connection.execute(text("""
                    ALTER TABLE translation 
                    CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """))
                print("已设置表的字符集为 utf8mb4")
                
                # 提交事务
                trans.commit()
                print("translation 表迁移完成!")
                
            except SQLAlchemyError as e:
                # 回滚事务
                trans.rollback()
                print(f"迁移过程中发生错误: {str(e)}")
                raise
                
    except Exception as e:
        print(f"连接数据库时发生错误: {str(e)}")
        raise

if __name__ == "__main__":
    migrate_translation_table()
