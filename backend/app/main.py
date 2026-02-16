"""
Virtual Try-On Shopify App - Backend API
FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
import structlog

from app.config import get_settings
from app.core.database import check_db_connection
from app.core.redis import check_redis_connection

# Import API routers
from app.api.v1 import auth, products, webhooks, sessions, measurements, recommendations, heatmap, tryon

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = structlog.get_logger()

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Backend API for Virtual Try-On Shopify App

    ## Features
    - 📸 Dual-pose body measurement extraction using MediaPipe
    - 👔 AI-powered size recommendations
    - 🎨 Fit visualization with heatmaps
    - 🤖 Virtual try-on image generation using Google Gemini
    - 🛍️ Seamless Shopify integration
    - ⚡ Redis-based caching for 24-hour image retention

    ## Tech Stack
    - **Framework:** FastAPI 0.104+
    - **Database:** PostgreSQL 15
    - **Cache:** Redis 7
    - **ML:** MediaPipe, OpenCV
    - **AI:** Google Gemini (nano-banana)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    debug=settings.APP_DEBUG,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(measurements.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(heatmap.router, prefix="/api/v1")
app.include_router(tryon.router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "online",
        "documentation": "/docs",
        "timestamp": datetime.utcnow().isoformat()
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancer and monitoring

    Checks:
    - API status
    - Database connection
    - Redis connection

    Returns:
    - 200 OK if all services are healthy
    - 503 Service Unavailable if any service is down
    """

    # Check database
    db_healthy = check_db_connection()

    # Check Redis
    redis_healthy = check_redis_connection()

    # Overall health
    healthy = db_healthy and redis_healthy

    status_code = 200 if healthy else 503

    response = {
        "status": "healthy" if healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "up",
            "database": "up" if db_healthy else "down",
            "redis": "up" if redis_healthy else "down",
        },
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION
    }

    return JSONResponse(content=response, status_code=status_code)


# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Run on application startup
    """
    logger.info(
        "application_started",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV
    )

    # Check database connection
    if check_db_connection():
        logger.info("database_connected", status="success")
    else:
        logger.error("database_connection_failed", status="error")

    # Check Redis connection
    if check_redis_connection():
        logger.info("redis_connected", status="success")
    else:
        logger.error("redis_connection_failed", status="error")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Run on application shutdown
    """
    logger.info(
        "application_shutdown",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions
    """
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=str(request.url.path),
        method=request.method,
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_DEBUG,
        log_level="info"
    )
