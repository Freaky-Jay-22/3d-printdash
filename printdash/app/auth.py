"""Password + session cookie for direct access (port 8090).

Access through the Home Assistant sidebar (ingress) is already protected by
the HA login and never needs this password.
"""
import hashlib
import hmac
import os
import secrets
import time

from .config import DATA_DIR

COOKIE = "pf_session"
SESSION_DAYS = 30
_ITER = 200_000


def _secret() -> bytes:
    path = os.path.join(DATA_DIR, "session.key")
    try:
        with open(path, "rb") as fh:
            key = fh.read()
            if len(key) >= 32:
                return key
    except OSError:
        pass
    key = secrets.token_bytes(32)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(key)
    return key


_SECRET = None


def secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        _SECRET = _secret()
    return _SECRET


def is_hashed(stored: str) -> bool:
    return str(stored or "").startswith("pbkdf2$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if is_hashed(stored):
        _, salt, digest = stored.split("$", 2)
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITER)
        return hmac.compare_digest(test.hex(), digest)
    return hmac.compare_digest(password, stored)  # legacy plain text


def make_token(stored: str, days: int = SESSION_DAYS) -> str:
    expires = int(time.time()) + days * 86400
    # binding to the stored hash logs everybody out when the password changes
    msg = f"{expires}|{stored[-24:]}".encode()
    sig = hmac.new(secret(), msg, hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def check_token(token: str, stored: str) -> bool:
    try:
        expires_s, sig = (token or "").split(".", 1)
        expires = int(expires_s)
    except ValueError:
        return False
    if expires < time.time():
        return False
    msg = f"{expires}|{stored[-24:]}".encode()
    good = hmac.new(secret(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)


# -- brake against password guessing ------------------------------------------
# Per client address: after MAX_FAILS wrong passwords within WINDOW seconds,
# further attempts from that address are refused until the window has passed.
MAX_FAILS = 5
WINDOW = 15 * 60
_fails: dict[str, list[float]] = {}


def _recent(ip: str) -> list:
    now = time.time()
    lst = [t for t in _fails.get(ip, []) if now - t < WINDOW]
    if lst:
        _fails[ip] = lst
    else:
        _fails.pop(ip, None)
    return lst


def blocked_for(ip: str) -> int:
    """Seconds until this address may try again (0 = not blocked)."""
    lst = _recent(ip or "?")
    if len(lst) < MAX_FAILS:
        return 0
    return max(1, int(lst[0] + WINDOW - time.time()))


def record_fail(ip: str) -> None:
    _recent(ip or "?")
    _fails.setdefault(ip or "?", []).append(time.time())
    if len(_fails) > 10_000:  # keep memory bounded
        _fails.clear()


def reset_fails(ip: str) -> None:
    _fails.pop(ip or "?", None)


# Basic auth is checked on every request; remember good passwords so the slow
# hash does not run each time (key = sha256 of password + stored hash).
_good: set[str] = set()


def verify_cached(password: str, stored: str) -> bool:
    key = hashlib.sha256(f"{password}\0{stored}".encode()).hexdigest()
    if key in _good:
        return True
    if verify_password(password, stored):
        if len(_good) > 100:
            _good.clear()
        _good.add(key)
        return True
    return False
