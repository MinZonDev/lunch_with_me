from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Float, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, date

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)
    role = Column(String(10), default="user", nullable=False)  # "user" | "admin"
    is_active = Column(Boolean, default=True, nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship("Member", foreign_keys=[member_id])


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    order_items = relationship("OrderItem", back_populates="member")
    deposits = relationship("Deposit", back_populates="member")
    reviews = relationship("Review", back_populates="member")


class DailyOrder(Base):
    __tablename__ = "daily_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_date = Column(Date, unique=True, nullable=False, index=True)
    status = Column(String(20), default="open", nullable=False)  # open | locked | finalized
    menu_link = Column(Text, nullable=True)
    menu_link_chay = Column(Text, nullable=True)
    total_bill = Column(Integer, default=0)  # đơn vị: nghìn đồng
    total_bill_chay = Column(Integer, default=0)  # đơn vị: nghìn đồng
    shared_cost_per_person = Column(Integer, default=0)  # tính sau khi finalize
    shared_cost_per_person_chay = Column(Integer, default=0)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("members.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    items = relationship("OrderItem", back_populates="daily_order", cascade="all, delete-orphan")
    creator = relationship("Member", foreign_keys=[created_by])


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    daily_order_id = Column(Integer, ForeignKey("daily_orders.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    dish_name = Column(String(200), nullable=True)  # Tên món thường
    dish_name_chay = Column(String(200), nullable=True)  # Tên món chay
    note = Column(Text, nullable=True)
    is_eating = Column(Boolean, default=False, nullable=False)  # Có ăn hay không
    is_chay = Column(Boolean, default=False, nullable=False)  # Ăn chay
    extra_item_description = Column(String(200), nullable=True)  # VD: "Cơm thêm + Trà tắc"
    extra_item_cost = Column(Integer, default=0)  # Giá món thêm (nghìn đồng)
    total_cost = Column(Integer, default=0)  # Tổng chi phí cá nhân (sau finalize)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Unique: mỗi member chỉ có 1 order item per daily order
    __table_args__ = (
        UniqueConstraint("daily_order_id", "member_id", name="uq_order_member"),
    )

    # Relationships
    daily_order = relationship("DailyOrder", back_populates="items")
    member = relationship("Member", back_populates="order_items")


class Deposit(Base):
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Số tiền nạp (nghìn đồng), có thể âm nếu rút
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    member = relationship("Member", back_populates="deposits")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    dish_name = Column(String(200), nullable=False)
    rating = Column(String(20), nullable=True)  # VD: "8/10"
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    member = relationship("Member", back_populates="reviews")
