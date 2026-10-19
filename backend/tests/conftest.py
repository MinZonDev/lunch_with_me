"""Shared test fixtures: in-memory fake Firestore + authenticated TestClient.

The API is tested end-to-end through FastAPI's TestClient. Firestore is
replaced by a small in-memory fake that supports the subset of the client
API the app uses: collection().document().get/set/update/delete,
where(...).limit(...).stream(), batch() and transaction(). The real
`get_db` dependency is overridden per-test, and `_next_id`'s transactional
decorator is neutralised so it runs against the fake directly.
"""
import operator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.database as database
from app.core.auth import create_access_token, hash_password
from app.database import get_db
from app.main import app as fastapi_app

# bcrypt is slow — hash the shared test password once for all seeded users
TEST_PASSWORD = "secret123"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)

_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda a, b: a in b,
}


# ---- Fake Firestore ----

class FakeSnapshot:
    def __init__(self, ref, data):
        self.reference = ref
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    @property
    def id(self):
        return self.reference.id

    def to_dict(self):
        return dict(self._data) if self._data is not None else None

    def get(self, field, transaction=None):
        return (self._data or {}).get(field)


class FakeDocRef:
    def __init__(self, db, col_name, doc_id):
        self._db = db
        self._col_name = col_name
        self.id = str(doc_id)

    def _col(self):
        return self._db._data.setdefault(self._col_name, {})

    def get(self, transaction=None):
        data = self._col().get(self.id)
        return FakeSnapshot(self, dict(data) if data is not None else None)

    def set(self, data):
        self._col()[self.id] = dict(data)

    def update(self, updates):
        if self.id not in self._col():
            raise KeyError(f"No document {self._col_name}/{self.id}")
        self._col()[self.id].update(updates)

    def delete(self):
        self._col().pop(self.id, None)


class FakeQuery:
    def __init__(self, db, col_name, filters=(), limit=None, orders=(), cursor=None):
        self._db = db
        self._col_name = col_name
        self._filters = filters
        self._limit = limit
        self._orders = orders
        self._cursor = cursor

    def _copy(self, **kw):
        state = dict(filters=self._filters, limit=self._limit, orders=self._orders, cursor=self._cursor)
        state.update(kw)
        return FakeQuery(self._db, self._col_name, **state)

    def where(self, field, op, value):
        return self._copy(filters=(*self._filters, (field, op, value)))

    def limit(self, n):
        return self._copy(limit=n)

    def select(self, _fields):
        return self  # projection only trims payload; tests see full docs

    def order_by(self, field, direction="ASCENDING"):
        return self._copy(orders=(*self._orders, (field, direction == "DESCENDING")))

    def start_after(self, values):
        return self._copy(cursor=values)

    def _sort_key(self, data):
        return tuple(data.get(f) for f, _ in self._orders)

    def stream(self):
        docs = self._db._data.get(self._col_name, {})
        rows = [(doc_id, data) for doc_id, data in list(docs.items())
                if all(_OPS[op](data.get(f), v) for f, op, v in self._filters)]
        # Stable multi-key sort, applied from the last key to the first
        for field, desc in reversed(self._orders):
            rows.sort(key=lambda r: r[1].get(field), reverse=desc)
        if self._cursor is not None:
            cur = tuple(self._cursor[f] for f, _ in self._orders)
            desc = self._orders[0][1]
            rows = [r for r in rows if (self._sort_key(r[1]) < cur if desc else self._sort_key(r[1]) > cur)]
        if self._limit is not None:
            rows = rows[:self._limit]
        return iter(FakeSnapshot(FakeDocRef(self._db, self._col_name, doc_id), dict(data))
                    for doc_id, data in rows)


class FakeCollection(FakeQuery):
    def document(self, doc_id):
        return FakeDocRef(self._db, self._col_name, doc_id)


class FakeBatch:
    def __init__(self):
        self._ops = []

    def set(self, ref, data):
        self._ops.append(lambda: ref.set(data))

    def update(self, ref, updates):
        self._ops.append(lambda: ref.update(updates))

    def delete(self, ref):
        self._ops.append(lambda: ref.delete())

    def commit(self):
        for op in self._ops:
            op()
        self._ops = []


class FakeTransaction:
    def set(self, ref, data):
        ref.set(data)

    def update(self, ref, updates):
        ref.update(updates)


class FakeFirestore:
    def __init__(self):
        self._data = {}

    def collection(self, name):
        return FakeCollection(self, name)

    def batch(self):
        return FakeBatch()

    def document(self, path):
        col, doc_id = path.split("/", 1)
        return FakeDocRef(self, col, doc_id)

    def get_all(self, refs, field_paths=None, transaction=None):
        return iter([ref.get() for ref in refs])

    def transaction(self):
        return FakeTransaction()


# ---- Seed helpers ----

def seed_member(db, member_id, name, is_active=True):
    db.collection("members").document(str(member_id)).set({
        "id": member_id,
        "name": name,
        "is_active": is_active,
        "is_admin": False,
        "created_at": datetime.now(timezone.utc),
    })


def seed_user(db, user_id, username, *, role="user", member_id=None,
              is_active=True, approved=True, email=None, full_name=None):
    db.collection("users").document(str(user_id)).set({
        "id": user_id,
        "username": username,
        "password_hash": TEST_PASSWORD_HASH,
        "full_name": full_name or username.title(),
        "email": email or f"{username}@test.local",
        "role": role,
        "is_active": is_active,
        "approved": approved,
        "member_id": member_id,
        "created_at": datetime.now(timezone.utc),
    })


def seed_deposit(db, dep_id, member_id, amount, *, status="approved",
                 dtype="deposit", note=None, created_at=None):
    db.collection("deposits").document(str(dep_id)).set({
        "id": dep_id,
        "member_id": member_id,
        "amount": amount,
        "note": note,
        "status": status,
        "type": dtype,
        "created_at": created_at or datetime.now(timezone.utc),
    })


def auth_headers(user_id, role="user"):
    token = create_access_token({"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


# ---- Fixtures ----

@pytest.fixture()
def db(monkeypatch):
    # _next_id wraps its inner function with fb_firestore.transactional,
    # which requires a real Transaction — bypass it for the fake.
    monkeypatch.setattr(database.fb_firestore, "transactional", lambda f: f)
    fake = FakeFirestore()
    # Seeded fixtures use low IDs (1, 2, ...); start counters high so IDs
    # minted by _next_id never collide with them.
    for name in ("users", "members", "daily_orders", "order_items", "deposits"):
        fake.collection("_counters").document(name).set({"value": 100})
    return fake


@pytest.fixture()
def client(db):
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        # No context manager: lifespan (init_db, scheduler) must not run in tests
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def sent_emails(monkeypatch):
    """Record outgoing emails instead of hitting SMTP."""
    import app.services.email_service as email_service
    calls = []
    for name in ("send_otp_email", "send_reset_password", "send_account_approved",
                 "send_blacklist_notice"):
        monkeypatch.setattr(email_service, name,
                            lambda *a, _n=name, **k: calls.append((_n, a, k)))
    return calls


@pytest.fixture()
def admin(db):
    seed_member(db, 1, "Admin")
    seed_user(db, 1, "admin", role="admin", member_id=1)
    return {"user_id": 1, "member_id": 1, "headers": auth_headers(1, "admin")}


@pytest.fixture()
def user(db):
    seed_member(db, 2, "Bình")
    seed_user(db, 2, "binh", member_id=2, full_name="Trần Bình")
    return {"user_id": 2, "member_id": 2, "headers": auth_headers(2)}
