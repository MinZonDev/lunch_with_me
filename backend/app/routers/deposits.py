from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Deposit, Member, OrderItem, DailyOrder
from app.schemas import DepositCreate, DepositResponse, MemberBalanceResponse
from app.core.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/deposits", tags=["deposits"])


@router.get("/summary", response_model=list[MemberBalanceResponse])
def get_deposit_summary(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    Get deposit summary for all active members:
    - total_deposited: Tổng tiền đã nạp
    - total_spent: Tổng tiền đã sử dụng (from finalized orders)
    - balance: Còn lại (deposited - spent)
    """
    members = db.query(Member).filter(Member.is_active == True).order_by(Member.name).all()

    result = []
    for member in members:
        # Total deposited
        total_deposited = (
            db.query(func.coalesce(func.sum(Deposit.amount), 0))
            .filter(Deposit.member_id == member.id)
            .scalar()
        )

        # Total spent (from finalized order items)
        total_spent = (
            db.query(func.coalesce(func.sum(OrderItem.total_cost), 0))
            .join(DailyOrder)
            .filter(
                OrderItem.member_id == member.id,
                DailyOrder.status == "finalized",
            )
            .scalar()
        )

        result.append(MemberBalanceResponse(
            id=member.id,
            name=member.name,
            total_deposited=total_deposited,
            total_spent=total_spent,
            balance=total_deposited - total_spent,
        ))

    return result


@router.get("", response_model=list[DepositResponse])
def list_deposits(member_id: int | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """List all deposit transactions, optionally filtered by member."""
    query = db.query(Deposit).join(Member)

    if member_id:
        query = query.filter(Deposit.member_id == member_id)

    deposits = query.order_by(Deposit.created_at.desc()).all()

    return [
        DepositResponse(
            id=d.id,
            member_id=d.member_id,
            member_name=d.member.name,
            amount=d.amount,
            note=d.note,
            created_at=d.created_at,
        )
        for d in deposits
    ]


@router.post("", response_model=DepositResponse, status_code=201)
def create_deposit(data: DepositCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Record a deposit (top-up) for a member."""
    member = db.query(Member).filter(Member.id == data.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    deposit = Deposit(
        member_id=data.member_id,
        amount=data.amount,
        note=data.note,
    )
    db.add(deposit)
    db.commit()
    db.refresh(deposit)

    return DepositResponse(
        id=deposit.id,
        member_id=deposit.member_id,
        member_name=member.name,
        amount=deposit.amount,
        note=deposit.note,
        created_at=deposit.created_at,
    )


@router.delete("/{deposit_id}", status_code=204)
def delete_deposit(deposit_id: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Delete a deposit transaction (admin only)."""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    db.delete(deposit)
    db.commit()
