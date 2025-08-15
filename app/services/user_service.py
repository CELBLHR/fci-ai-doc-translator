"""
用户管理服务
处理SSO用户创建、同步和权限管理
"""
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from flask import current_app
from flask_login import login_user

from app import db
from app.models.user import User, Role
from app.utils.timezone_helper import now_with_timezone

logger = logging.getLogger(__name__)


class UserService:
    """用户管理服务"""
    
    @staticmethod
    def find_or_create_sso_user(user_info: Dict[str, Any], provider: str) -> Tuple[User, bool]:
        """
        查找或创建SSO用户
        
        Args:
            user_info: SSO提供的用户信息
            provider: SSO提供者名称
            
        Returns:
            Tuple[User, bool]: (用户对象, 是否为新创建)
        """
        username = user_info.get('username')
        email = user_info.get('email')
        
        if not username:
            raise ValueError("用户名不能为空")
        
        # 尝试通过用户名和邮箱同时查找
        user = User.query.filter_by(username=username, email=email).first()
        
        if user:
            # 更新现有用户信息
            UserService._update_user_from_sso(user, user_info, provider)
            return user, False
        
        # 检查是否允许自动创建用户
        if not current_app.config.get('SSO_AUTO_CREATE_USER', True):
            raise ValueError("用户不存在且不允许自动创建")
        
        # 创建新用户
        user = UserService._create_sso_user(user_info, provider)
        return user, True
    
    @staticmethod
    def _create_sso_user(user_info: Dict[str, Any], provider: str) -> User:
        """创建SSO用户"""
        try:
            # 获取默认角色
            default_role_name = current_app.config.get('SSO_DEFAULT_ROLE', 'user')
            default_role = Role.query.filter_by(name=default_role_name).first()
            
            if not default_role:
                logger.warning(f"默认角色 '{default_role_name}' 不存在，创建基础角色")
                default_role = UserService._ensure_default_role(default_role_name)
            
            # 创建用户
            user = User(
                username=user_info['username'],
                email=user_info.get('email', ''),
                first_name=user_info.get('first_name', ''),
                last_name=user_info.get('last_name', ''),
                display_name=user_info.get('display_name', ''),
                sso_provider=provider,
                sso_subject=user_info.get('sub', ''),
                status='approved',  # SSO用户默认已审批
                role=default_role,
                register_time=now_with_timezone()
            )
            
            # SSO用户不需要密码，设置一个随机值
            import secrets
            user.set_password(secrets.token_urlsafe(32))
            
            db.session.add(user)
            db.session.commit()
            
            logger.info(f"创建SSO用户成功: {user.username} (provider: {provider})")
            return user
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建SSO用户失败: {e}")
            raise
    
    @staticmethod
    def _update_user_from_sso(user: User, user_info: Dict[str, Any], provider: str):
        """从SSO信息更新用户"""
        try:
            # 更新用户信息
            if user_info.get('email') and user_info['email'] != user.email:
                user.email = user_info['email']
            
            if user_info.get('first_name') and user_info['first_name'] != user.first_name:
                user.first_name = user_info['first_name']
            
            if user_info.get('last_name') and user_info['last_name'] != user.last_name:
                user.last_name = user_info['last_name']
            
            if user_info.get('display_name') and user_info['display_name'] != user.display_name:
                user.display_name = user_info['display_name']
            
            # 更新SSO相关信息
            user.sso_provider = provider
            user.sso_subject = user_info.get('sub', '')
            user.last_login = now_with_timezone()
            
            # 处理组/角色映射
            UserService._update_user_roles_from_groups(user, user_info.get('groups', []))
            
            db.session.commit()
            logger.info(f"更新SSO用户信息: {user.username}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新SSO用户失败: {e}")
            raise
    
    @staticmethod
    def _update_user_roles_from_groups(user: User, groups: list):
        """根据SSO组信息更新用户角色"""
        if not groups:
            return
        
        # 这里可以实现组到角色的映射逻辑
        # 例如：如果用户在 'admin' 组中，给予管理员角色
        group_role_mapping = current_app.config.get('SSO_GROUP_ROLE_MAPPING', {
            'admin': 'admin',
            'administrators': 'admin',
            'users': 'user'
        })
        
        for group in groups:
            if group in group_role_mapping:
                role_name = group_role_mapping[group]
                role = Role.query.filter_by(name=role_name).first()
                if role and user.role != role:
                    logger.info(f"根据组 '{group}' 更新用户 '{user.username}' 角色为 '{role_name}'")
                    user.role = role
                    break
    
    @staticmethod
    def _ensure_default_role(role_name: str) -> Role:
        """确保默认角色存在"""
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)
            db.session.commit()
            logger.info(f"创建默认角色: {role_name}")
        return role
    
    @staticmethod
    def login_sso_user(user: User, remember: bool = True) -> bool:
        """登录SSO用户"""
        try:
            # 检查用户状态
            if user.status != 'approved':
                logger.warning(f"用户 {user.username} 状态不是已审批: {user.status}")
                return False
            
            # 使用Flask-Login登录用户
            login_success = login_user(user, remember=remember)
            
            if login_success:
                # 更新最后登录时间
                user.last_login = now_with_timezone()
                db.session.commit()
                
                logger.info(f"SSO用户登录成功: {user.username}")
                return True
            else:
                logger.error(f"SSO用户登录失败: {user.username}")
                return False
                
        except Exception as e:
            logger.error(f"SSO用户登录异常: {e}")
            return False
    
    @staticmethod
    def get_user_by_sso_subject(subject: str, provider: str) -> Optional[User]:
        """根据SSO主题ID查找用户"""
        return User.query.filter_by(
            sso_subject=subject,
            sso_provider=provider
        ).first()
    
    @staticmethod
    def is_sso_user(user: User) -> bool:
        """检查是否为SSO用户"""
        return bool(user.sso_provider)
    
    @staticmethod
    def can_change_password(user: User) -> bool:
        """检查用户是否可以修改密码"""
        return not UserService.is_sso_user(user)
    
    @staticmethod
    def sync_user_from_sso(user: User, user_info: Dict[str, Any]) -> bool:
        """同步SSO用户信息"""
        try:
            UserService._update_user_from_sso(user, user_info, user.sso_provider)
            return True
        except Exception as e:
            logger.error(f"同步SSO用户信息失败: {e}")
            return False


class SSOUserManager:
    """SSO用户管理器"""
    
    def __init__(self):
        self.user_service = UserService()
    
    def authenticate_sso_user(self, sso_data: Dict[str, Any]) -> Tuple[bool, Optional[User], str]:
        """
        认证SSO用户
        
        Args:
            sso_data: SSO回调数据
            
        Returns:
            Tuple[bool, Optional[User], str]: (是否成功, 用户对象, 消息)
        """
        try:
            provider = sso_data.get('provider', 'unknown')
            user_info = sso_data.get('user_info', {})
            
            if not user_info:
                return False, None, "未获取到用户信息"
            
            # 查找或创建用户
            user, is_new = self.user_service.find_or_create_sso_user(user_info, provider)
            
            # 登录用户
            if self.user_service.login_sso_user(user):
                message = "新用户注册并登录成功" if is_new else "登录成功"
                return True, user, message
            else:
                return False, None, "登录失败"
                
        except Exception as e:
            logger.error(f"SSO用户认证失败: {e}")
            return False, None, f"认证失败: {str(e)}"
    
    def handle_sso_logout(self, user: User) -> bool:
        """处理SSO登出"""
        try:
            # 这里可以添加SSO登出的特殊处理逻辑
            # 例如：调用SSO提供者的登出API
            logger.info(f"处理SSO用户登出: {user.username}")
            return True
        except Exception as e:
            logger.error(f"处理SSO登出失败: {e}")
            return False


# 全局SSO用户管理器实例
sso_user_manager = SSOUserManager()
