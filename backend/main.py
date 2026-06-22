import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes.align import router as align_router
from app.api.routes.auth import router as auth_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.users import router as users_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="AlignAI Backend API",
    description=(
        "FastAPI service for EU AI Act compliance auditing with LangGraph agent integration. "
        "Provides authentication, session management, and Server-Sent Events streaming for AI-powered compliance reports."
    ),
    version="0.1.0",
    contact={
        "name": "AlignAI Project",
        "url": "https://github.com/yourusername/alignai",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(users_router)
app.include_router(align_router)
