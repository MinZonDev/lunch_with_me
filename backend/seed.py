"""Seed Firestore: chỉ tạo tài khoản admin mặc định."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.database import init_db, get_db, _next_id
from app.core.auth import hash_password
from datetime import datetime, timezone


def seed():
    init_db()
    db = get_db()

    admin_existing = list(db.collection("users").where("username", "==", "admin").limit(1).stream())
    if not admin_existing:
        user_id = _next_id(db, "users")
        db.collection("users").document(str(user_id)).set({
            "id": user_id,
            "username": "admin",
            "password_hash": hash_password("admin123"),
            "full_name": "Admin",
            "email": "admin@lunchme.local",
            "date_of_birth": None,
            "role": "admin",
            "is_active": True,
            "member_id": None,
            "created_at": datetime.now(timezone.utc),
        })
        print("+ User: admin / admin123 (ĐỔI MẬT KHẨU NGAY!)")
    else:
        print("= User admin đã tồn tại")

    print("Seed done!")


if __name__ == "__main__":
    seed()
