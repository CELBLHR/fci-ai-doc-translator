#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
设置用户为管理员的脚本
使用方法：python set_admin.py <user_id>
"""
import sys
import os
import argparse
from datetime import datetime

# 将项目根目录添加到路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User, Role
from app.utils.timezone_helper import now_with_timezone

def set_user_as_admin(user_id):
    """
    将指定ID的用户设置为管理员
    
    Args:
        user_id: 用户ID
    
    Returns:
        bool: 操作是否成功
    """
    # 创建应用上下文
    app = create_app()
    
    with app.app_context():
        # 查找用户
        user = User.query.get(user_id)
        if not user:
            print(f"错误: 找不到ID为 {user_id} 的用户")
            return False
        
        # 查找管理员角色
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            print("错误: 找不到管理员角色，正在创建...")
            admin_role = Role(name='admin')
            db.session.add(admin_role)
            try:
                db.session.commit()
                print("成功创建管理员角色")
            except Exception as e:
                db.session.rollback()
                print(f"创建管理员角色失败: {str(e)}")
                return False
        
        # 检查用户是否已经是管理员
        if user.role_id == admin_role.id:
            print(f"用户 {user.username} (ID: {user.id}) 已经是管理员")
            return True
        
        # 设置用户为管理员
        user.role = admin_role
        
        # 如果用户状态为pending，则设置为approved
        if user.status == 'pending':
            user.status = 'approved'
            user.approve_time = now_with_timezone()
            print(f"用户状态已从 'pending' 更改为 'approved'")
        
        # 提交更改
        try:
            db.session.commit()
            print(f"成功将用户 {user.username} (ID: {user.id}) 设置为管理员")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"设置管理员失败: {str(e)}")
            return False

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='设置用户为管理员')
    parser.add_argument('user_id', type=int, help='要设置为管理员的用户ID')
    parser.add_argument('-f', '--force', action='store_true', help='强制执行，不询问确认')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 确认操作
    if not args.force:
        confirm = input(f"确定要将用户ID {args.user_id} 设置为管理员吗? (y/n): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
    
    # 执行设置管理员操作
    success = set_user_as_admin(args.user_id)
    
    # 返回适当的退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 