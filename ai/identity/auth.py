import jwt
import bcrypt
import time
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24


def _load_jwt_secret() -> str:
    env_secret = os.environ.get("NYX_JWT_SECRET") or os.environ.get("SNOWOS_JWT_SECRET")
    if env_secret:
        return env_secret

    secret_path = os.environ.get(
        "SNOWOS_JWT_SECRET_FILE",
        os.path.expanduser("~/.snowos/jwt.secret"),
    )
    os.makedirs(os.path.dirname(secret_path), exist_ok=True)

    if os.path.exists(secret_path):
        with open(secret_path, "r", encoding="utf-8") as handle:
            secret = handle.read().strip()
            if secret:
                return secret

    secret = secrets.token_urlsafe(48)
    with open(secret_path, "w", encoding="utf-8") as handle:
        handle.write(secret)
    os.chmod(secret_path, 0o600)
    return secret


JWT_SECRET = _load_jwt_secret()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None # Token expired
    except jwt.InvalidTokenError:
        return None # Invalid token
