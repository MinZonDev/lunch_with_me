from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import members, orders, order_items, deposits, reviews, auth

app = FastAPI(
    title="Lunch With Me API",
    description="Hệ thống đặt cơm nhóm - Quản lý order, chia tiền, theo dõi deposit",
    version="1.0.0",
)

# CORS - allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(members.router)
app.include_router(orders.router)
app.include_router(order_items.router)
app.include_router(deposits.router)
app.include_router(reviews.router)


@app.on_event("startup")
def on_startup():
    """Initialize database tables on startup."""
    init_db()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Lunch With Me API is running 🍚"}
