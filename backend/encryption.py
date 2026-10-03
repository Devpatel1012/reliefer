import base64
import hashlib
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

_raw_key = os.getenv("ENCRYPTION_KEY", os.getenv("JWT_SECRET_KEY", "default_reliefer_secret_key_12345"))
# Derive a valid 32-byte url-safe base64 key for Fernet from whatever secret key is provided
_derived_key = base64.urlsafe_b64encode(hashlib.sha256(_raw_key.encode()).digest())
_fernet = Fernet(_derived_key)


def encrypt_string(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_string(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        # Fallback if text was stored as plain text previously
        return ciphertext
