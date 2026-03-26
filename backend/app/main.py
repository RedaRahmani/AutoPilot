from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.api.routes.auth import router as auth_router

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(auth_router)