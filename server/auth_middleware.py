import jwt
from functools import wraps
from flask import request, jsonify

JWT_SECRET = 'fvo_secret_key_2024'

def authenticate_token(f):
    """Decorator — checks JWT token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Access token required'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            request.user = decoded  # { id, employee_id, name, role }
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired. Please login again.'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token. Please login again.'}), 403
        
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Use AFTER authenticate_token for admin-only routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated