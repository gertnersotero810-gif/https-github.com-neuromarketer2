from fastapi import APIRouter
from app.api.v1.endpoints import auth, import_router, agents, dashboard

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(import_router.router)
api_router.include_router(agents.router)
api_router.include_router(dashboard.router)

