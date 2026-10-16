import pytest
from cryptography.fernet import Fernet

from app.security import SecretBox, SecretDecryptError, hash_password, mask_secret, verify_password


def test_password_roundtrip():
    h = hash_password("abcd1234")
    assert verify_password("abcd1234", h)
    assert not verify_password("abcd12345", h)


def test_verify_garbage_hash_is_false():
    assert verify_password("x", "not-a-hash") is False


def test_secretbox_roundtrip_and_wrong_key():
    k1, k2 = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    t = SecretBox(k1).encrypt("sk-abc")
    assert SecretBox(k1).decrypt(t) == "sk-abc"
    with pytest.raises(SecretDecryptError):
        SecretBox(k2).decrypt(t)


def test_mask_secret():
    assert mask_secret("sk-12345678") == "****5678"
    assert mask_secret("abc") == "****"
