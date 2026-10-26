"""Public response models for the free collective pickup feature."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Participant(BaseModel):
    id: int
    name: str


class PickupSession(BaseModel):
    id: str
    order_id: int
    participants: list[Participant]
    votes: dict[str, int]
    skipped: list[int]
    scores: dict[str, int]
    status: Literal['random', 'ready', 'finalized', 'cancelled']
    selected_ids: list[int]
    created_by: int
    created_at: datetime
    finalized_at: datetime | None = None
    finalized_by: int | None = None
    cancelled_at: datetime | None = None
    cancelled_by: int | None = None
    ranking: list[dict] = Field(default_factory=list)
    notifications: dict | None = None


class PickupState(BaseModel):
    method: Literal['legacy', 'collective']
    session: PickupSession | None
