from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member
from app.schemas import MemberCreate, MemberUpdate, MemberResponse
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("", response_model=list[MemberResponse])
def list_members(active_only: bool = True, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """List all members, optionally filtered by active status."""
    query = db.query(Member)
    if active_only:
        query = query.filter(Member.is_active == True)
    return query.order_by(Member.name).all()


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(member_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Get a single member by ID."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.post("", response_model=MemberResponse, status_code=201)
def create_member(data: MemberCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Create a new team member."""
    existing = db.query(Member).filter(Member.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Member with this name already exists")

    member = Member(name=data.name, is_admin=data.is_admin)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberResponse)
def update_member(member_id: int, data: MemberUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Update a member's info."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if data.name is not None:
        # Check for name conflict
        existing = db.query(Member).filter(Member.name == data.name, Member.id != member_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Name already taken")
        member.name = data.name

    if data.is_active is not None:
        member.is_active = data.is_active

    if data.is_admin is not None:
        member.is_admin = data.is_admin

    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Soft-delete a member (set inactive)."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member.is_active = False
    db.commit()
