import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging_config import setup_logging
from app.database import init_db
from app.routers import members, orders, order_items, deposits, reviews, auth
from app.routers import reports, admin_router, restaurants, reminders, delegations, be_menu
from app.middleware.logging_middleware import LoggingMiddleware
from app.schemas import FrontendLogEntry

setup_logging()
logger = logging.getLogger("lwm.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Lunch With Me API...")
    init_db()
    try:
        from app.services.scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        logger.info("Scheduler started")
        yield
        stop_scheduler()
        logger.info("Scheduler stopped")
    except ImportError:
        yield
    logger.info("API shutdown complete")


app = FastAPI(
    title="Lunch With Me API",
    description="Hệ thống đặt cơm nhóm - Quản lý order, chia tiền, theo dõi deposit",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://lunch-with-me-psi.vercel.app",
    ],
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
app.include_router(reminders.router)
app.include_router(delegations.router)
app.include_router(be_menu.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Lunch With Me API is running"}


@app.post("/api/logs", status_code=204)
def receive_frontend_log(entry: FrontendLogEntry, request: Request):
    """Nhận error logs từ frontend."""
    fe_logger = logging.getLogger("lwm.frontend")
    level = entry.level.upper()
    msg = "[FE] %s | url=%s | ctx=%s"
    args = (entry.message, entry.url or "-", entry.context or {})
    if level == "ERROR":
        fe_logger.error(msg, *args)
    elif level == "WARN":
        fe_logger.warning(msg, *args)
    else:
        fe_logger.info(msg, *args)
