from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from app.database import get_db, _next_id
from app.schemas import ReviewCreate, ReviewResponse
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewResponse])
def list_reviews(db=Depends(get_db), _=Depends(get_current_user)):
    reviews = [s.to_dict() for s in db.collection("reviews").stream()]
    reviews.sort(key=lambda r: r["created_at"], reverse=True)

    member_names: dict[int, str] = {}
    result = []
    for r in reviews:
        mid = r.get("member_id")
        if mid and mid not in member_names:
            m_doc = db.collection("members").document(str(mid)).get()
            member_names[mid] = m_doc.to_dict().get("name") if m_doc.exists else None
        result.append(ReviewResponse(
            id=r["id"],
            member_id=mid,
            member_name=member_names.get(mid) if mid else None,
            dish_name=r["dish_name"],
            rating=r.get("rating"),
            comment=r.get("comment"),
            created_at=r["created_at"],
        ))
    return result


@router.post("", response_model=ReviewResponse, status_code=201)
def create_review(data: ReviewCreate, db=Depends(get_db), _=Depends(get_current_user)):
    member_name = None
    if data.member_id:
        m_doc = db.collection("members").document(str(data.member_id)).get()
        if not m_doc.exists:
            raise HTTPException(status_code=404, detail="Member not found")
        member_name = m_doc.to_dict().get("name")

    rev_id = _next_id(db, "reviews")
    now = datetime.now(timezone.utc)
    doc_data = {
        "id": rev_id,
        "member_id": data.member_id,
        "dish_name": data.dish_name,
        "rating": data.rating,
        "comment": data.comment,
        "created_at": now,
    }
    db.collection("reviews").document(str(rev_id)).set(doc_data)

    return ReviewResponse(
        id=rev_id,
        member_id=data.member_id,
        member_name=member_name,
        dish_name=data.dish_name,
        rating=data.rating,
        comment=data.comment,
        created_at=now,
    )


@router.delete("/{review_id}", status_code=204)
def delete_review(review_id: int, db=Depends(get_db), _=Depends(get_current_admin)):
    ref = db.collection("reviews").document(str(review_id))
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Review not found")
    ref.delete()
