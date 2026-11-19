import pytest
from cryptography.exceptions import InvalidTag

import config
from core import security
from core.security import SessionManager, TemplateVault
import numpy as np


# ---- UT-S: passwords --------------------------------------------------------
def test_password_hash_verifies():
    h = security.hash_password("Secret123")
    assert security.verify_password("Secret123", h)


def test_wrong_password_rejected():
    assert not security.verify_password("Secret124", security.hash_password("Secret123"))


def test_hashes_are_salted_and_never_plaintext():
    a, b = security.hash_password("Secret123"), security.hash_password("Secret123")
    assert a != b and "Secret123" not in a and a.startswith("$2")


@pytest.mark.parametrize("pw,ok", [("short1", False), ("lettersonly", False), ("12345678", False),
                                   ("x" * 80 + "1", False), ("Valid1234", True)])
def test_password_policy(pw, ok):
    assert (security.password_problem(pw) is None) == ok


def test_malformed_hash_does_not_crash():
    assert security.verify_password("x", "not-a-hash") is False


# ---- UT-S: encrypted template vault ----------------------------------------
def test_vault_roundtrip(vault):
    arr = np.random.default_rng(1).normal(size=(5, 128))
    path = vault.save("CSC/2023/001", arr)
    assert np.allclose(vault.load(path), arr)


def test_vault_file_is_not_plaintext(vault):
    path = vault.save("CSC/2023/001", np.ones((5, 128)))
    raw = open(path, "rb").read()
    assert b"NUMPY" not in raw and b"\x93NUMPY" not in raw


def test_vault_detects_tampering(vault):
    path = vault.save("CSC/2023/001", np.ones((5, 128)))
    raw = bytearray(open(path, "rb").read())
    raw[40] ^= 0xFF
    open(path, "wb").write(bytes(raw))
    with pytest.raises(InvalidTag):
        vault.load(path)


def test_vault_rejects_wrong_key(tmp_path, vault):
    path = vault.save("CSC/2023/001", np.ones((5, 128)))
    other = TemplateVault(tmp_path / "t2", tmp_path / "keys2" / "k.key")
    with pytest.raises(InvalidTag):
        other.load(path)


def test_vault_key_is_256_bit_and_reused(tmp_path):
    kp = tmp_path / "k" / "key"
    TemplateVault(tmp_path / "t", kp)
    first = kp.read_bytes()
    TemplateVault(tmp_path / "t", kp)
    assert len(first) == 32 and kp.read_bytes() == first


def test_vault_delete(vault):
    path = vault.save("CSC/2023/001", np.ones((5, 128)))
    vault.delete(path)
    assert not __import__("os").path.exists(path)


# ---- UT-S: session manager ----------------------------------------------------
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_session_token_is_random_and_valid():
    c = Clock()
    s1, s2 = SessionManager(30, c), SessionManager(30, c)
    t1, t2 = s1.start({"u": 1}), s2.start({"u": 1})
    assert t1 != t2 and len(t1) >= 40 and s1.validate(t1)


def test_session_idle_timeout():
    c = Clock()
    s = SessionManager(30, c)
    tok = s.start({"u": 1})
    c.t += 30 * 60 + 1
    assert not s.validate(tok) and not s.active


def test_session_activity_extends_life():
    c = Clock()
    s = SessionManager(30, c)
    tok = s.start({"u": 1})
    c.t += 29 * 60
    s.touch()
    c.t += 29 * 60
    assert s.validate(tok)


def test_session_rejects_forged_token():
    s = SessionManager(30, Clock())
    s.start({"u": 1})
    assert not s.validate("forged-token") and not s.validate(None)


# ---- UT-S: validation -----------------------------------------------------------
@pytest.mark.parametrize("v,ok", [("CSC/2023/001", True), ("csc-2023-01", True), ("1", False), ("a b c d e", False),
                                  ("'; DROP TABLE x;--", False)])
def test_matric_validation(v, ok):
    assert security.valid_matric(v) == ok


@pytest.mark.parametrize("v,ok", [("a@b.org", True), ("no-at-sign", False), ("a@b", False), ("a b@c.org", False)])
def test_email_validation(v, ok):
    assert security.valid_email(v) == ok
