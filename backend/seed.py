"""Seed Firestore with team members and default admin user."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.database import init_db, get_db, _next_id
from app.core.auth import hash_password
from datetime import datetime, timezone

TEAM_MEMBERS = [
    "Hiếu",
    "Trọng",
    "Kiêm",
    "Anh Dũng",
    "Hoàng Anh",
    "Lê Thành Công",
    "Tùng",
    "Sỹ",
    "Việt",
    "Vinh",
    "Hòa",
    "Hieuthuhai",
]


def seed():
    init_db()
    db = get_db()

    # Seed members
    existing = {s.to_dict()["name"] for s in db.collection("members").stream()}
    added = 0
    member_map = {}

    for name in TEAM_MEMBERS:
        if name not in existing:
            new_id = _next_id(db, "members")
            db.collection("members").document(str(new_id)).set({
                "id": new_id,
                "name": name,
                "is_active": True,
                "is_admin": False,
                "created_at": datetime.now(timezone.utc),
            })
            member_map[name] = new_id
            added += 1
            print(f"  + Member: {name}")
        else:
            snap = list(db.collection("members").where("name", "==", name).limit(1).stream())
            member_map[name] = snap[0].to_dict()["id"]
            print(f"  = Member: {name} (already exists)")

    print(f"\nAdded {added} new members.")

    # Seed default admin user
    admin_existing = list(db.collection("users").where("username", "==", "admin").limit(1).stream())
    if not admin_existing:
        hieu_id = member_map.get("Hiếu")
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
            "member_id": hieu_id,
            "created_at": datetime.now(timezone.utc),
        })
        print("\n  + User: admin / admin123 (CHANGE THIS PASSWORD!)")
    else:
        print("\n  = User: admin (already exists)")

    print("\nSeed done!")


if __name__ == "__main__":
    seed()
