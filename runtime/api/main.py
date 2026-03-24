"""FastAPI main application for runtime."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from .routes import runs, events, artifacts, patches, approvals, ci, security


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Product Runtime API",
        description="Runtime API for bounded coding workspace",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Exception handler
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    # Include routers
    app.include_router(runs.router, prefix="/runs", tags=["runs"])
    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
    app.include_router(patches.router, prefix="/patches", tags=["patches"])
    app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
    app.include_router(ci.router, prefix="/ci", tags=["ci"])
    app.include_router(security.router, prefix="/security", tags=["security"])
    
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint."""
        return {
            "name": "Product Runtime API",
            "version": "1.0.0",
            "docs": "/docs"
        }
    
    return app


# Create the app instance
app = create_app()
