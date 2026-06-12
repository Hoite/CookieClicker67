"""
Authentication utilities for Cookie Clicker 67
Handles password hashing, JWT tokens, and session management
"""

import bcrypt
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

# Import from global jwt
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
JWT_EXPIRY_DAYS = 7

def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, password_hash):
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False

def generate_jwt_token(user_id, username):
    """Generate a JWT token valid for 7 days"""
    payload = {
        'user_id': str(user_id),
        'username': username,
        'exp': datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS),
        'iat': datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_jwt_token(token):
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def validate_username(username):
    """Validate username format"""
    if not username or len(username) < 3 or len(username) > 20:
        return False
    if not all(c.isalnum() or c == '_' for c in username):
        return False
    return True

def validate_password(password):
    """Validate password strength"""
    if not password or len(password) < 6:
        return False
    return True
