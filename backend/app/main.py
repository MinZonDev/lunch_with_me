from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import members, orders, order_items, deposits, reviews, auth
from app.routers import reports, admin_router, restaurants


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        from app.services.scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        yield
        stop_scheduler()
    except ImportError:
        yield


app = FastAPI(
    title="Lunch With Me API",
    description="Hệ thống đặt cơm nhóm - Quản lý order, chia tiền, theo dõi deposit",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(orders.router)
app.include_router(order_items.router)
app.include_router(deposits.router)
app.include_router(reviews.router)
app.include_router(reports.router)
app.include_router(admin_router.router)
app.include_router(restaurants.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Lunch With Me API is running 🍚"}
