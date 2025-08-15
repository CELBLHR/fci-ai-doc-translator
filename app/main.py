"""
应用主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, translation, log_management
from app.utils.logger import get_logger

# 创建应用实例
app = FastAPI(title="翻译系统")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建主日志记录器
logger = get_logger("main")

# 注册路由
app.include_router(auth.router)
app.include_router(translation.router)
app.include_router(log_management.router)

@app.get("/")
async def root():
    """根路由"""
    logger.info("访问根路由")
    return {"message": "翻译系统API服务"} 