import logging

logger = logging.getLogger("lwm.delegation")


def has_active_delegation(db, grantor_member_id: int, delegate_member_id: int) -> bool:
    """Return True if delegate_member_id has been authorised by grantor_member_id."""
    results = list(
        db.collection("delegations")
        .where("grantor_member_id", "==", grantor_member_id)
        .where("delegate_member_id", "==", delegate_member_id)
        .where("status", "==", "active")
        .limit(1)
        .stream()
    )
    return bool(results)


def get_delegated_member_ids(db, delegate_member_id: int) -> list[int]:
    """Return list of member_ids that have authorised delegate_member_id to order for them."""
    results = list(
        db.collection("delegations")
        .where("delegate_member_id", "==", delegate_member_id)
        .where("status", "==", "active")
        .stream()
    )
    return [r.to_dict()["grantor_member_id"] for r in results]
