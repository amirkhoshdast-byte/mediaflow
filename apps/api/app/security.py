import base64
import hashlib
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.config import get_settings

_hasher = PasswordHasher()
ALGO = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        # Derive a stable key from SECRET_KEY so dev setups work; production sets ENCRYPTION_KEY.
        key = base64.urlsafe_b64encode(
            hashlib.sha256(get_settings().secret_key.encode()).digest()
        ).decode()
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def make_token(user_id: str, purpose: str, minutes: int) -> str:
    exp = datetime.now(UTC) + timedelta(minutes=minutes)
    return jwt.encode(
        {"sub": user_id, "purpose": purpose, "exp": exp}, get_settings().secret_key, algorithm=ALGO
    )


def read_token(token: str, purpose: str) -> str | None:
    """Return the user id if the token is valid and has the expected purpose."""
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=[ALGO])
    except jwt.PyJWTError:
        return None
    if data.get("purpose") != purpose:
        return None
    return data.get("sub")
