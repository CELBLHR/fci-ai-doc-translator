import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'

    # SSO配置
    SSO_ENABLED = os.environ.get('SSO_ENABLED', 'false').lower() == 'true'
    SSO_PROVIDER = os.environ.get('SSO_PROVIDER', 'oauth2')  # oauth2, saml, oidc
    SSO_AUTO_CREATE_USER = os.environ.get('SSO_AUTO_CREATE_USER', 'true').lower() == 'true'
    SSO_DEFAULT_ROLE = os.environ.get('SSO_DEFAULT_ROLE', 'user')

    # OAuth2/OIDC配置
    OAUTH2_CLIENT_ID = os.environ.get('OAUTH2_CLIENT_ID', '')
    OAUTH2_CLIENT_SECRET = os.environ.get('OAUTH2_CLIENT_SECRET', '')
    OAUTH2_AUTHORIZATION_URL = os.environ.get('OAUTH2_AUTHORIZATION_URL', '')
    OAUTH2_TOKEN_URL = os.environ.get('OAUTH2_TOKEN_URL', '')
    OAUTH2_USERINFO_URL = os.environ.get('OAUTH2_USERINFO_URL', '')
    OAUTH2_SCOPE = os.environ.get('OAUTH2_SCOPE', 'openid profile email')
    OAUTH2_REDIRECT_URI = os.environ.get('OAUTH2_REDIRECT_URI', 'http://localhost:5000/auth/sso/callback')

    # SAML配置
    SAML_SP_ENTITY_ID = os.environ.get('SAML_SP_ENTITY_ID', 'http://localhost:5000')
    SAML_SP_ACS_URL = os.environ.get('SAML_SP_ACS_URL', 'http://localhost:5000/auth/sso/saml/acs')
    SAML_SP_SLS_URL = os.environ.get('SAML_SP_SLS_URL', 'http://localhost:5000/auth/sso/saml/sls')
    SAML_IDP_ENTITY_ID = os.environ.get('SAML_IDP_ENTITY_ID', '')
    SAML_IDP_SSO_URL = os.environ.get('SAML_IDP_SSO_URL', '')
    SAML_IDP_SLS_URL = os.environ.get('SAML_IDP_SLS_URL', '')
    SAML_IDP_X509_CERT = os.environ.get('SAML_IDP_X509_CERT', '')

    # 用户属性映射配置
    SSO_USER_MAPPING = {
        'username': os.environ.get('SSO_ATTR_USERNAME', 'preferred_username'),
        'email': os.environ.get('SSO_ATTR_EMAIL', 'email'),
        'first_name': os.environ.get('SSO_ATTR_FIRST_NAME', 'given_name'),
        'last_name': os.environ.get('SSO_ATTR_LAST_NAME', 'family_name'),
        'display_name': os.environ.get('SSO_ATTR_DISPLAY_NAME', 'name'),
        'groups': os.environ.get('SSO_ATTR_GROUPS', 'groups')
    }

    # 文件存储基础配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 200 * 1024 * 1024))  # 默认200MB
    
    # 文件存储配额配置（单位：字节）
    USER_STORAGE_QUOTA = int(os.environ.get('USER_STORAGE_QUOTA', 1024 * 1024 * 1024))  # 默认1GB
    
    # 文件清理策略配置
    FILE_CLEANUP_DAYS = int(os.environ.get('FILE_CLEANUP_DAYS', 7))  # 默认7天后清理
    TEMP_FILE_CLEANUP_HOURS = int(os.environ.get('TEMP_FILE_CLEANUP_HOURS', 24))  # 临时文件24小时后清理
    
    # 文件类型配置
    ALLOWED_EXTENSIONS = {
        'ppt': {'ppt', 'pptx'},
        'pdf': {'pdf'},
        'annotation': {'json'}
    }
    
    # 文件目录结构配置
    UPLOAD_SUBDIRS = {
        'ppt': 'ppt',
        'pdf': 'pdf',
        'annotation': 'annotations',
        'temp': 'temp'
    }
    
    # 从环境变量构建数据库URI
    DB_TYPE = os.environ.get('DB_TYPE', 'mysql')
    DB_USER = os.environ.get('DB_USER', '')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'ppt_translate_db')
    
    # 额外的数据库连接配置
    DB_CONNECT_TIMEOUT = int(os.environ.get('DB_CONNECT_TIMEOUT', 10))
    DB_POOL_SIZE = int(os.environ.get('DB_POOL_SIZE', 100))  # 修改默认值为100
    DB_USE_SSL = os.environ.get('DB_USE_SSL', 'false').lower() == 'true'
    
    # 构建数据库URI
    if DB_TYPE == 'mysql':
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        
        # SQLAlchemy连接池配置
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': DB_POOL_SIZE,
            'pool_timeout': 30,
            'pool_recycle': 3600,
            'connect_args': {
                'connect_timeout': DB_CONNECT_TIMEOUT
            }
        }
        
        # 如果启用SSL
        if DB_USE_SSL:
            SQLALCHEMY_ENGINE_OPTIONS['connect_args']['ssl'] = {
                'ssl_mode': 'REQUIRED'
            }
    else:
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///users.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    # 开发环境文件大小限制
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB
    # 开发环境可以设置较小的配额
    USER_STORAGE_QUOTA = 100 * 1024 * 1024  # 100MB
    FILE_CLEANUP_DAYS = 1  # 1天后清理
    TEMP_FILE_CLEANUP_HOURS = 1  # 1小时后清理

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境文件大小限制
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB

class TestingConfig(Config):
    TESTING = True
    # 测试环境文件大小限制
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB
    # 测试环境使用内存数据库
    if Config.DB_TYPE == 'sqlite':
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # 测试环境使用较小的配额
    USER_STORAGE_QUOTA = 10 * 1024 * 1024  # 10MB
    FILE_CLEANUP_DAYS = 1
    TEMP_FILE_CLEANUP_HOURS = 1

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# 其他配置从环境变量获取
base_model_file = os.environ.get('BASE_MODEL_FILE', r'D:\project\system\model')
api_key = os.environ.get('API_KEY', ''  # set via API_KEY env var)
data_file = os.environ.get('DATA_FILE', r'D:\project\system\app\pythonProjectnewman\data_3\bjsp_dict_merged.json')