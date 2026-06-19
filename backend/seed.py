"""Seed database with team members and default admin user."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, init_db
from app.models import Member, User
from app.core.auth import hash_password

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
    db = SessionLocal()
    try:
        # Seed members
        existing = {m.name for m in db.query(Member).all()}
        added = 0
        member_map = {}
        for name in TEAM_MEMBERS:
            if name not in existing:
                m = Member(name=name, is_active=True)
                db.add(m)
                db.flush()
                member_map[name] = m.id
                added += 1
                print(f"  + Member: {name}")
            else:
                m = db.query(Member).filter(Member.name == name).first()
                member_map[name] = m.id
                print(f"  = Member: {name} (already exists)")
        db.commit()
        print(f"\nAdded {added} new members.")

        # Seed default admin user
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            hiếu_id = member_map.get("Hiếu")
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="Admin",
                email="admin@lunchme.local",
                role="admin",
                member_id=hiếu_id,
            )
            db.add(admin)
            db.commit()
            print("\n  + User: admin / admin123 (CHANGE THIS PASSWORD!)")
        else:
            print("\n  = User: admin (already exists)")

        print("\nSeed done!")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
