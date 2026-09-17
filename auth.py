"""
统一认证模块 - JWT
"""
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

SECRET_KEY = os.environ.get('JWT_SECRET', 'change-me-in-production')
TOKEN_EXPIRE_HOURS = 72


def generate_token(user_id, role, extra=None):
    """生成 JWT token"""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token):
    """解码 JWT token"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(roles=None):
    """装饰器：验证 token"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = None
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

            if not token:
                return jsonify({'success': False, 'error': '未登录'}), 401

            payload = decode_token(token)
            if not payload:
                return jsonify({'success': False, 'error': '登录已过期'}), 401

            if roles and payload.get('role') not in roles:
                return jsonify({'success': False, 'error': '无权限'}), 403

            request.user = payload
            return f(*args, **kwargs)
        return wrapper
    return decorator
