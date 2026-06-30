from pydantic import BaseModel, Field, EmailStr
from datetime import date, datetime
from typing import Optional


# ============== Auth Schemas ==============

class LoginRequest(BaseModel):
    username: str
    password: str


class SendOtpRequest(BaseModel):
    email: str = Field(..., max_length=255)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=255)
    date_of_birth: Optional[date] = None
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RegisterPendingResponse(BaseModel):
    message: str
    username: str
    email: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=255)
    date_of_birth: Optional[date] = None
    role: str = Field(default="user", pattern="^(user|admin)$")
    member_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[date] = None
    avatar_url: Optional[str] = None
    member_id: Optional[int] = None
    role: Optional[str] = Field(None, pattern="^(user|admin)$")  # admin only


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    nickname: Optional[str] = None
    email: str
    date_of_birth: Optional[date] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    approved: bool = True
    member_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Member Schemas ==============

class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    is_admin: bool = False


class MemberUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class MemberResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    is_admin: bool
    username: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Daily Order Schemas ==============

class RestaurantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    link: Optional[str] = None


class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    link: Optional[str] = None
    is_active: Optional[bool] = None


class RestaurantResponse(BaseModel):
    id: int
    name: str
    link: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderLinkItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1)


class DailyOrderCreate(BaseModel):
    order_date: date
    name: Optional[str] = None           # Tên menu, VD: "Cơm", "Phở"
    restaurant_id: Optional[int] = None
    menu_link: Optional[str] = None
    deadline_time: Optional[str] = None  # "HH:MM" VN time, default from config
    note: Optional[str] = None
    created_by: Optional[int] = None


class DailyOrderUpdate(BaseModel):
    total_bill: Optional[int] = None
    note: Optional[str] = None
    status: Optional[str] = None


class DailyOrderLinksUpdate(BaseModel):
    links: list[OrderLinkItem] = []


class DailyOrderFinalize(BaseModel):
    total_bill: int = Field(..., ge=0)


class OrderItemInOrder(BaseModel):
    id: int
    member_id: int
    member_name: str
    dish_name: Optional[str] = None
    note: Optional[str] = None
    is_eating: bool
    extra_item_description: Optional[str] = None
    extra_item_cost: int
    total_cost: int

    model_config = {"from_attributes": True}


class DailyOrderResponse(BaseModel):
    id: int
    order_date: date
    name: Optional[str] = None
    status: str
    restaurant_id: Optional[int] = None
    restaurant_name: Optional[str] = None
    links: list[OrderLinkItem] = []
    order_deadline: Optional[datetime] = None
    minutes_remaining: Optional[int] = None  # computed, not stored
    total_bill: int
    shared_cost_per_person: int
    note: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    items: list[OrderItemInOrder] = []
    eater_count: int = 0

    model_config = {"from_attributes": True}


class DailyOrderListResponse(BaseModel):
    id: int
    order_date: date
    name: Optional[str] = None
    status: str
    total_bill: int
    eater_count: int = 0
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Order Item Schemas ==============

class OrderItemCreate(BaseModel):
    member_id: int
    dish_name: Optional[str] = None
    note: Optional[str] = None


class OrderItemUpdate(BaseModel):
    dish_name: Optional[str] = None
    note: Optional[str] = None


class OrderItemExtraUpdate(BaseModel):
    extra_item_description: Optional[str] = None
    extra_item_cost: int = Field(default=0, ge=0)


class OrderItemResponse(BaseModel):
    id: int
    daily_order_id: int
    member_id: int
    member_name: str
    dish_name: Optional[str] = None
    note: Optional[str] = None
    is_eating: bool
    extra_item_description: Optional[str] = None
    extra_item_cost: int
    total_cost: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Deposit Schemas ==============

class DepositCreate(BaseModel):
    amount: int = Field(..., ge=1, description="Số tiền (nghìn đồng)")
    note: Optional[str] = None
    member_id: Optional[int] = None  # admin only: deposit for another member


class ChargeCreate(BaseModel):
    member_id: int
    amount: int = Field(..., ge=1, description="Số tiền bị trừ (nghìn đồng)")
    note: Optional[str] = None


class DepositResponse(BaseModel):
    id: int
    member_id: int
    member_name: str
    amount: int
    note: Optional[str] = None
    status: str  # pending | approved
    type: str = "deposit"  # deposit | charge
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberBalanceResponse(BaseModel):
    id: int
    name: str
    username: Optional[str] = None
    email: Optional[str] = None
    total_deposited: int
    total_charged: int  # khoản chi ngoài
    total_spent: int
    balance: int

    model_config = {"from_attributes": True}


# ============== Report Schemas ==============

class ReportMemberRow(BaseModel):
    member_id: int
    member_name: str
    days_eaten: int
    total_cost: int

class ReportDayRow(BaseModel):
    order_date: date
    total_bill: int
    eater_count: int

class ReportResponse(BaseModel):
    period_label: str
    days: list[ReportDayRow]
    members: list[ReportMemberRow]
    grand_total: int

# ============== Deposit History Schemas ==============

class MemberDailyCost(BaseModel):
    member_id: int
    member_name: str
    daily_costs: dict  # date_str -> cost
    total_spent: int

class DepositHistoryResponse(BaseModel):
    month: int
    year: int
    dates: list[str]
    members: list[MemberDailyCost]

# ============== Review Schemas ==============

class ReviewCreate(BaseModel):
    member_id: Optional[int] = None
    dish_name: str = Field(..., min_length=1)
    rating: Optional[str] = None
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    member_id: Optional[int] = None
    member_name: Optional[str] = None
    dish_name: str
    rating: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Delegation Schemas ==============

class DelegationCreate(BaseModel):
    delegate_member_id: int  # người được ủy quyền (sẽ đặt giùm tôi)


class DelegationResponse(BaseModel):
    id: int
    grantor_member_id: int   # người ủy quyền
    grantor_name: str
    delegate_member_id: int  # người được ủy quyền
    delegate_name: str
    status: str              # active | revoked
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Spending Schema ==============

class SpendingItemResponse(BaseModel):
    daily_order_id: int
    order_date: date
    order_name: Optional[str] = None
    dish_name: Optional[str] = None
    total_cost: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Member Detail Schemas ==============

class MemberTransactionItem(BaseModel):
    type: str  # "deposit" | "charge" | "spending"
    date: datetime
    amount: int
    description: Optional[str] = None
    status: Optional[str] = None
    order_date: Optional[date] = None
    daily_order_id: Optional[int] = None
    running_balance: int = 0


class MemberDetailResponse(BaseModel):
    member_id: int
    member_name: str
    total_deposited: int
    total_charged: int
    total_spent: int
    balance: int
    transactions: list[MemberTransactionItem]


# ============== Frontend Log Schema ==============

class FrontendLogEntry(BaseModel):
    level: str
    message: str
    context: Optional[dict] = None
    timestamp: Optional[str] = None
    url: Optional[str] = None
