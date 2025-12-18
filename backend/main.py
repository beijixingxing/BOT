from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from backend.routes import chat_router, admin_router, knowledge_router, public_api_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import AsyncSessionLocal
from backend.services import MemoryService, BlacklistService
import os

scheduler = AsyncIOScheduler()


async def scheduled_memory_summary():
    async with AsyncSessionLocal() as db:
        from backend.services import UserService
        user_service = UserService(db)
        memory_service = MemoryService(db)
        
        users = await user_service.get_all_users(limit=1000)
        for user in users:
            try:
                await memory_service.summarize_user(user.id)
            except Exception as e:
                print(f"Error summarizing user {user.id}: {e}")


async def cleanup_expired_bans():
    async with AsyncSessionLocal() as db:
        service = BlacklistService(db)
        count = await service.cleanup_expired()
        if count > 0:
            print(f"Cleaned up {count} expired bans")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    scheduler.add_job(
        scheduled_memory_summary,
        CronTrigger(hour=3),
        id="memory_summary",
        replace_existing=True
    )
    scheduler.add_job(
        cleanup_expired_bans,
        CronTrigger(minute="*/30"),
        id="cleanup_bans",
        replace_existing=True
    )
    scheduler.start()
    
    yield
    
    scheduler.shutdown()


app = FastAPI(
    title="CatieBot API",
    description="Backend API for CatieBot Discord Bot",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(knowledge_router)
app.include_router(public_api_router)

templates_dir = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
static_dir = os.path.join(os.path.dirname(__file__), "..", "web", "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
    
    @app.get("/admin")
    async def admin_page(request: Request):
        return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/")
async def root():
    return {"message": "CatieBot API is running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
