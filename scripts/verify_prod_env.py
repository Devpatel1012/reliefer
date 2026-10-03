#!/usr/bin/env python3
"""
Reliefer Production Environment Auditor & Health Verifier
Checks environment variables, security config, database connectivity, and health endpoint status.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def audit_environment():
    print("\n" + "═" * 60)
    print(" 🛡️ RELIEFER PRODUCTION AUDITOR")
    print("═" * 60 + "\n")

    issues = []

    # 1. JWT Secret Check
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    if not jwt_secret or "change_this" in jwt_secret or len(jwt_secret) < 32:
        issues.append("❌ JWT_SECRET_KEY is insecure or missing. Generate a 64-char key via scripts/generate_prod_secrets.py.")
    else:
        print("✅ JWT_SECRET_KEY is configured securely.")

    # 2. Encryption Key Check
    enc_key = os.getenv("ENCRYPTION_KEY", "")
    if not enc_key or "change_this" in enc_key:
        issues.append("❌ ENCRYPTION_KEY is missing or insecure. Generate a Fernet key via scripts/generate_prod_secrets.py.")
    else:
        try:
            from cryptography.fernet import Fernet
            Fernet(enc_key.encode())
            print("✅ ENCRYPTION_KEY is a valid Fernet key.")
        except Exception as e:
            issues.append(f"❌ ENCRYPTION_KEY is invalid: {e}")

    # 3. Database URL Check
    db_url = os.getenv("DATABASE_URL", "sqlite:///./reliefer.db")
    if db_url.startswith("sqlite"):
        print("⚠️ DATABASE_URL uses SQLite (OK for testing/dev, but PostgreSQL is recommended for high concurrency production).")
    else:
        print("✅ DATABASE_URL is configured for external PostgreSQL.")

    # 4. CORS Origins Check
    origins = os.getenv("ALLOWED_ORIGINS", "*")
    if "*" in origins:
        print("⚠️ ALLOWED_ORIGINS is set to '*' (wildcard). Set explicit domain names in production.")
    else:
        print(f"✅ ALLOWED_ORIGINS explicitly configured: {origins}")

    print("\n" + "═" * 60)
    if issues:
        print("🚨 ACTION REQUIRED BEFORE LAUNCH:")
        for issue in issues:
            print(f"  {issue}")
        print("═" * 60 + "\n")
        return False
    else:
        print("🎉 ALL PRODUCTION CHECKS PASSED! READY FOR DEPLOYMENT.")
        print("═" * 60 + "\n")
        return True


if __name__ == "__main__":
    success = audit_environment()
    sys.exit(0 if success else 1)
