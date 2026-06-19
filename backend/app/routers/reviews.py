from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Review, Member
from app.schemas import ReviewCreate, ReviewResponse
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewResponse])
def list_reviews(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """List all dish reviews."""
    reviews = db.query(Review).order_by(Review.created_at.desc()).all()
    return [
        ReviewResponse(
            id=r.id,
            member_id=r.member_id,
            member_name=r.member.name if r.member else None,
            dish_name=r.dish_name,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in reviews
    ]


@router.post("", response_model=ReviewResponse, status_code=201)
def create_review(data: ReviewCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Add a new dish review."""
    member = None
    if data.member_id:
        member = db.query(Member).filter(Member.id == data.member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

    review = Review(
        member_id=data.member_id,
        dish_name=data.dish_name,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return ReviewResponse(
        id=review.id,
        member_id=review.member_id,
        member_name=member.name if member else None,
        dish_name=review.dish_name,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


@router.delete("/{review_id}", status_code=204)
def delete_review(review_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Delete a review."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()
