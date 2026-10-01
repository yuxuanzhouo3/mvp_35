import hashlib
import hmac
import secrets

from app.core.errors import AppError

ITERATIONS = 120_000


def hash_password(password: str, *, min_length: int = 8) -> str:
    if len(password) < min_length:
        raise AppError("WEAK_PASSWORD", f"密码至少 {min_length} 位")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return hmac.compare_digest(check, digest)
