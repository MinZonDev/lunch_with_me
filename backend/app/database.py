"""Firebase Firestore client and helpers."""

import os
from datetime import date, datetime
from types import SimpleNamespace

import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore


def init_db():
    """Initialize Firebase app. Safe to call multiple times."""
    if firebase_admin._apps:
        return
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if cred_path:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()  # uses GOOGLE_APPLICATION_CREDENTIALS


def get_db():
    """FastAPI dependency: return Firestore client."""
    return fb_firestore.client()


def _next_id(db, collection_name: str) -> int:
    """Atomically increment and return the next integer ID for a collection."""
    ref = db.collection("_counters").document(collection_name)

    @fb_firestore.transactional
    def _update(transaction, doc_ref):
        snap = doc_ref.get(transaction=transaction)
        current = (snap.get("value") or 0) if snap.exists else 0
        new_val = current + 1
        transaction.set(doc_ref, {"value": new_val})
        return new_val

    return _update(db.transaction(), ref)


# ---- Date/Datetime conversion helpers ----

_DATE_FIELDS = {"order_date", "date_of_birth"}


def _to_ns(data: dict) -> SimpleNamespace:
    """
    Convert a Firestore document dict to a SimpleNamespace.
    - String fields named in _DATE_FIELDS are converted to date objects.
    - Firestore Timestamp fields come back as timezone-aware datetimes (kept as-is).
    """
    fixed = {}
    for k, v in data.items():
        if isinstance(v, str) and k in _DATE_FIELDS:
            try:
                fixed[k] = date.fromisoformat(v)
            except ValueError:
                fixed[k] = None
        else:
            fixed[k] = v
    return SimpleNamespace(**fixed)


def _doc_ns(doc) -> SimpleNamespace | None:
    """Convert a Firestore DocumentSnapshot to SimpleNamespace, or None if missing."""
    if not doc.exists:
        return None
    return _to_ns(doc.to_dict())
