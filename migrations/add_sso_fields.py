#!/usr/bin/env python3
"""
数据库迁移脚本：添加SSO相关字段
为User表添加SSO支持所需的字段
"""
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.user import User, Role
from sqlalchemy import text

def upgrade_database():
    """升级数据库，添加SSO字段"""
    app = create_app()
    
    with app.app_context():
        try:
            print("开始数据库迁移：添加SSO字段...")
            
            # 检查字段是否已存在
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            # 添加email字段
            if 'email' not in columns:
                print("添加email字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN email VARCHAR(120)'))
                print("✅ email字段添加成功")
            else:
                print("email字段已存在，跳过")
            
            # 添加first_name字段
            if 'first_name' not in columns:
                print("添加first_name字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN first_name VARCHAR(50)'))
                print("✅ first_name字段添加成功")
            else:
                print("first_name字段已存在，跳过")
            
            # 添加last_name字段
            if 'last_name' not in columns:
                print("添加last_name字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN last_name VARCHAR(50)'))
                print("✅ last_name字段添加成功")
            else:
                print("last_name字段已存在，跳过")
            
            # 添加display_name字段
            if 'display_name' not in columns:
                print("添加display_name字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN display_name VARCHAR(100)'))
                print("✅ display_name字段添加成功")
            else:
                print("display_name字段已存在，跳过")
            
            # 添加sso_provider字段
            if 'sso_provider' not in columns:
                print("添加sso_provider字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN sso_provider VARCHAR(50)'))
                print("✅ sso_provider字段添加成功")
            else:
                print("sso_provider字段已存在，跳过")
            
            # 添加sso_subject字段
            if 'sso_subject' not in columns:
                print("添加sso_subject字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN sso_subject VARCHAR(255)'))
                print("✅ sso_subject字段添加成功")
            else:
                print("sso_subject字段已存在，跳过")
            
            # 添加last_login字段
            if 'last_login' not in columns:
                print("添加last_login字段...")
                db.engine.execute(text('ALTER TABLE users ADD COLUMN last_login DATETIME'))
                print("✅ last_login字段添加成功")
            else:
                print("last_login字段已存在，跳过")
            
            # 创建索引
            try:
                print("创建索引...")
                db.engine.execute(text('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)'))
                db.engine.execute(text('CREATE INDEX IF NOT EXISTS idx_users_sso_provider ON users(sso_provider)'))
                db.engine.execute(text('CREATE INDEX IF NOT EXISTS idx_users_sso_subject ON users(sso_subject)'))
                print("✅ 索引创建成功")
            except Exception as e:
                print(f"⚠️ 索引创建失败（可能已存在）: {e}")
            
            print("🎉 数据库迁移完成！")
            
        except Exception as e:
            print(f"❌ 数据库迁移失败: {e}")
            raise


def downgrade_database():
    """降级数据库，移除SSO字段"""
    app = create_app()
    
    with app.app_context():
        try:
            print("开始数据库降级：移除SSO字段...")
            
            # 移除字段（注意：SQLite不支持DROP COLUMN）
            db_type = db.engine.url.drivername
            
            if 'sqlite' in db_type:
                print("⚠️ SQLite不支持删除列，跳过降级操作")
                return
            
            # MySQL/PostgreSQL支持删除列
            sso_columns = [
                'email', 'first_name', 'last_name', 'display_name',
                'sso_provider', 'sso_subject', 'last_login'
            ]
            
            for column in sso_columns:
                try:
                    db.engine.execute(text(f'ALTER TABLE users DROP COLUMN {column}'))
                    print(f"✅ {column}字段删除成功")
                except Exception as e:
                    print(f"⚠️ {column}字段删除失败: {e}")
            
            print("🎉 数据库降级完成！")
            
        except Exception as e:
            print(f"❌ 数据库降级失败: {e}")
            raise


def create_default_roles():
    """创建默认角色"""
    app = create_app()
    
    with app.app_context():
        try:
            print("创建默认角色...")
            
            # 检查并创建admin角色
            admin_role = Role.query.filter_by(name='admin').first()
            if not admin_role:
                admin_role = Role(name='admin')
                db.session.add(admin_role)
                print("✅ 创建admin角色")
            else:
                print("admin角色已存在")
            
            # 检查并创建user角色
            user_role = Role.query.filter_by(name='user').first()
            if not user_role:
                user_role = Role(name='user')
                db.session.add(user_role)
                print("✅ 创建user角色")
            else:
                print("user角色已存在")
            
            db.session.commit()
            print("🎉 默认角色创建完成！")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 默认角色创建失败: {e}")
            raise


def check_migration_status():
    """检查迁移状态"""
    app = create_app()
    
    with app.app_context():
        try:
            print("检查数据库迁移状态...")
            
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            sso_columns = [
                'email', 'first_name', 'last_name', 'display_name',
                'sso_provider', 'sso_subject', 'last_login'
            ]
            
            print("\nSSO字段状态:")
            for column in sso_columns:
                status = "✅ 存在" if column in columns else "❌ 不存在"
                print(f"  {column}: {status}")
            
            # 检查角色
            admin_role = Role.query.filter_by(name='admin').first()
            user_role = Role.query.filter_by(name='user').first()
            
            print("\n默认角色状态:")
            print(f"  admin: {'✅ 存在' if admin_role else '❌ 不存在'}")
            print(f"  user: {'✅ 存在' if user_role else '❌ 不存在'}")
            
            # 检查SSO用户
            sso_users = User.query.filter(User.sso_provider.isnot(None)).count()
            print(f"\nSSO用户数量: {sso_users}")
            
        except Exception as e:
            print(f"❌ 检查迁移状态失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SSO数据库迁移工具')
    parser.add_argument('action', choices=['upgrade', 'downgrade', 'status', 'roles'], 
                       help='执行的操作')
    
    args = parser.parse_args()
    
    if args.action == 'upgrade':
        upgrade_database()
        create_default_roles()
    elif args.action == 'downgrade':
        downgrade_database()
    elif args.action == 'status':
        check_migration_status()
    elif args.action == 'roles':
        create_default_roles()


if __name__ == '__main__':
    main()
