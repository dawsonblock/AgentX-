"""FastAPI main application."""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from db.session import init_db, engine
from db.base import Base
from core.config import Settings
from core.logging import get_logger
from api.routes import runs, approvals, patches, artifacts

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting AgentX API...")
    
    # Validate config
    errors = Settings.validate()
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AgentX API...")
    engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="AgentX API",
    description="Bounded coding workspace with LLM agents",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
app.include_router(patches.router, prefix="/patches", tags=["patches"])
app.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agentx"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "AgentX API",
        "version": "1.0.0",
        "docs": "/docs"
    }
