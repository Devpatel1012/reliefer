#!/usr/bin/env python3
"""
Reliefer Production Secret Generator
Generates secure random keys for JWT_SECRET_KEY and Fernet ENCRYPTION_KEY.
"""

import secrets
from cryptography.fernet import Fernet


def generate_secrets():
    jwt_secret = secrets.token_hex(32)  # 64-char hex string
    fernet_key = Fernet.generate_key().decode("utf-8")

    print("\n" + "═" * 60)
    print(" 🚀 RELIEFER PRODUCTION SECRETS GENERATOR")
    print("═" * 60 + "\n")
    print("Copy and paste these secrets into your production environment settings:\n")
    print(f"JWT_SECRET_KEY={jwt_secret}")
    print(f"ENCRYPTION_KEY={fernet_key}")
    print("\n" + "═" * 60 + "\n")


if __name__ == "__main__":
    generate_secrets()
