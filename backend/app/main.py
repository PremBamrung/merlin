from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import youtube
from backend.app.core.config import settings
from backend.app.models.database import init_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    youtube.router, prefix=f"{settings.API_V1_STR}/youtube", tags=["youtube"]
)


@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/")
def read_root():
    return {
        "message": "Welcome to Merlin API",
        "docs_url": "/docs",
        "openapi_url": f"{settings.API_V1_STR}/openapi.json",
    }
