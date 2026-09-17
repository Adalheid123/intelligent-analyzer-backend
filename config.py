"""
统一配置
"""
import os


class Config:
    # ========== 数据库 ==========
    # 优先读环境变量；没有则用兜底值（Supabase）
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres.vefydrqnckeoshpxaknt:yyq200509131421@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres'
    )

    # 兼容 Railway 老格式 postgres:// → postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ========== JWT ==========
    JWT_SECRET = os.environ.get(
        'JWT_SECRET',
        'kj8sdf92hfsd98fh2sdf98h2sdf'
    )
    JWT_EXPIRE_HOURS = 72

    # ========== CORS ==========
    ALLOWED_ORIGINS = os.environ.get(
        'ALLOWED_ORIGINS',
        '*'
    ).split(',')
