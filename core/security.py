"""Security services: password hashing, AES-256-GCM template vault,
idle-timeout session tokens and input validation."""
from __future__ import annotations

import io
import os
import re
import secrets
import time
from pathlib import Path

import bcrypt
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import config

_AAD = b"SAFR-template-v1"
_MATRIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/\-_.]{4,19}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z '\-.]{0,49}$")


# ---------------------------------------------------------------- passwords
def hash_password(password: str, rounds: int | None = None) -> str:
    salt = bcrypt.gensalt(rounds or config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def password_problem(password: str) -> str | None:
    """Return a human-readable reason if the password is unacceptable."""
    if len(password) < config.MIN_PASSWORD_LENGTH:
        return f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters long."
    if len(password.encode("utf-8")) > 72:
        return "Password is too long (72 bytes maximum)."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must contain both letters and digits."
    return None


# --------------------------------------------------------------- validation
def valid_matric(value: str) -> bool:
    return bool(_MATRIC_RE.match(value or ""))


def valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value or "")) and len(value) <= 100


def valid_name(value: str) -> bool:
    return bool(_NAME_RE.match(value or ""))


# ------------------------------------------------------------ template vault
class TemplateVault:
    """Stores facial encodings as AES-256-GCM encrypted files.

    Only the 128-dimensional encoding vectors are stored - never the raw
    photographs - and every file is authenticated, so any tampering is
    detected at load time.
    """

    def __init__(self, directory: str | Path | None = None, key_path: str | Path | None = None):
        self.directory = Path(directory or config.TEMPLATE_DIR)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._aes = AESGCM(self._load_or_create_key(Path(key_path or config.KEY_PATH)))

    @staticmethod
    def _load_or_create_key(path: Path) -> bytes:
        if path.exists():
            key = path.read_bytes()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            key = AESGCM.generate_key(bit_length=256)
            path.write_bytes(key)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        if len(key) != 32:
            raise ValueError("Template key must be exactly 32 bytes (AES-256).")
        return key

    def seal(self, array: np.ndarray) -> bytes:
        buf = io.BytesIO()
        np.save(buf, np.asarray(array, dtype=np.float64), allow_pickle=False)
        nonce = os.urandom(12)
        return nonce + self._aes.encrypt(nonce, buf.getvalue(), _AAD)

    def open(self, blob: bytes) -> np.ndarray:
        nonce, ciphertext = blob[:12], blob[12:]
        plain = self._aes.decrypt(nonce, ciphertext, _AAD)  # raises InvalidTag if tampered
        return np.load(io.BytesIO(plain), allow_pickle=False)

    def save(self, matric: str, array: np.ndarray) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", matric)
        path = self.directory / f"{safe}.enc"
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(self.seal(array))
        os.replace(tmp, path)          # atomic: a power cut never leaves a half-written file
        return str(path)

    def load(self, path: str | Path) -> np.ndarray:
        return self.open(Path(path).read_bytes())

    def delete(self, path: str | Path | None) -> None:
        if path:
            Path(path).unlink(missing_ok=True)


# ----------------------------------------------------------------- sessions
class SessionManager:
    """Issues an unguessable token at login and enforces an idle timeout."""

    def __init__(self, timeout_minutes: float | None = None, clock=time.monotonic):
        self.timeout = (timeout_minutes if timeout_minutes is not None else config.SESSION_TIMEOUT_MIN) * 60
        self._clock = clock
        self.token: str | None = None
        self.user: dict | None = None
        self._last = 0.0

    @property
    def active(self) -> bool:
        return self.token is not None

    def start(self, user: dict) -> str:
        self.user = dict(user)
        self.token = secrets.token_urlsafe(32)
        self._last = self._clock()
        return self.token

    def validate(self, token: str | None) -> bool:
        """True while the token is genuine and the session has not idled out."""
        if not self.active or token is None or not secrets.compare_digest(token, self.token):
            return False
        if self._clock() - self._last > self.timeout:
            self.end()
            return False
        self._last = self._clock()
        return True

    def touch(self) -> None:
        if self.active:
            self._last = self._clock()

    def remaining(self) -> int:
        if not self.active:
            return 0
        return max(0, int(self.timeout - (self._clock() - self._last)))

    def expired(self) -> bool:
        return self.active and self.remaining() == 0

    def end(self) -> None:
        self.token = None
        self.user = None
