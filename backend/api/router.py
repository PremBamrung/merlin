"""Master APIRouter — mounts all sub-routers."""

from fastapi import APIRouter

from backend.api.chat import router as chat_router
from backend.api.digest import router as digest_router
from backend.api.graph import router as graph_router
from backend.api.knowledge import router as knowledge_router
from backend.api.share import router as share_router
from backend.api.sources.youtube import router as youtube_router
from backend.api.tags import router as tags_router
from backend.api.tasks import router as tasks_router

api_router = APIRouter(prefix="/api")

api_router.include_router(chat_router)
api_router.include_router(digest_router)
api_router.include_router(graph_router)
api_router.include_router(knowledge_router)
api_router.include_router(share_router)
api_router.include_router(tags_router)
api_router.include_router(tasks_router)
api_router.include_router(youtube_router)
