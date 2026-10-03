import sys
import os

from database import SessionLocal
import models

db = SessionLocal()
user = db.query(models.User).first()

latest = db.query(models.GeneratedResume).filter(models.GeneratedResume.user_id == user.id).order_by(models.GeneratedResume.created_at.desc()).first()
print(f"LATEST RESUME CONTENT:\n{latest.content[:500] if latest else 'None'}")

if latest:
    print("\n\n---\n\nLet's check if the raw content has line breaks...")
    print(repr(latest.content[:200]))

