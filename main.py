"""
Main FastAPI application entry point for Telegram Assistant.
This is the main application file for local development.
For serverless deployment, use the api/ directory endpoints.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from src.core.config import settings
from src.core.logger import get_logger, setup_logging
from src.core.database import create_tables, health_check, get_database_session
from src.core.exceptions import TelegramAssistantException, create_error_response

# Setup logging
setup_logging()
logger = get_logger(__name__)


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info(f"Starting Telegram Assistant v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    try:
        # Initialize database
        logger.info("Initializing database...")
        await create_tables()

        # Perform health checks
        logger.info("Performing startup health checks...")
        health_status = await health_check()

        if health_status["status"] != "healthy":
            logger.warning(f"Health check issues detected: {health_status}")

        # Validate configuration
        logger.info("Validating configuration...")
        from src.core.config import validate_configuration, print_configuration_status

        config_status = validate_configuration()
        if not config_status["valid"]:
            logger.error("Configuration validation failed!")
            for error in config_status["errors"]:
                logger.error(f"  - {error}")
        else:
            logger.info("Configuration validation passed")

        # Print configuration status in development
        if settings.is_development:
            print_configuration_status()

        logger.info("Application startup completed successfully")

        yield

    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise

    finally:
        logger.info("Application shutdown initiated")
        # Add cleanup tasks here if needed
        logger.info("Application shutdown completed")


# =============================================================================
# FASTAPI APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI-powered Telegram bot for document analysis and conversational AI",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan
)

# =============================================================================
# MIDDLEWARE SETUP
# =============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# GLOBAL EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(TelegramAssistantException)
async def telegram_assistant_exception_handler(request, exc: TelegramAssistantException):
    """Handle custom application exceptions."""
    logger.error(f"Application exception: {exc.to_dict()}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=create_error_response(exc)
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "HTTPException",
                "message": exc.detail,
                "code": f"HTTP_{exc.status_code}"
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected exception: {exc}", exc_info=True)

    error_response = {
        "success": False,
        "error": {
            "type": "InternalServerError",
            "message": "An unexpected error occurred",
            "code": "INTERNAL_SERVER_ERROR"
        }
    }

    # Include error details in development
    if settings.is_development:
        error_response["error"]["details"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


# =============================================================================
# HEALTH AND STATUS ENDPOINTS
# =============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint - basic application information."""
    return {
        "success": True,
        "message": f"Welcome to {settings.app_name} v{settings.version}",
        "status": "running",
        "environment": settings.environment,
        "docs_url": "/docs" if settings.is_development else None
    }


@app.get("/health", tags=["Health"])
async def health_endpoint():
    """Health check endpoint."""
    try:
        health_status = await health_check()
        return {
            "success": True,
            "data": health_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error": {
                    "type": "HealthCheckFailed",
                    "message": "Health check failed",
                    "details": str(e) if settings.is_development else None
                }
            }
        )


@app.get("/status", tags=["Health"])
async def status_endpoint():
    """Detailed status endpoint."""
    try:
        # Get configuration status
        from src.core.config import validate_configuration
        config_status = validate_configuration()

        # Get database health
        db_health = await health_check()

        return {
            "success": True,
            "data": {
                "application": {
                    "name": settings.app_name,
                    "version": settings.version,
                    "environment": settings.environment,
                    "debug": settings.debug
                },
                "configuration": config_status,
                "database": db_health,
                "services": {
                    "telegram": bool(settings.telegram_bot_token),
                    "google_gemini": bool(settings.google_gemini_api_key),
                    "pinecone": settings.use_pinecone,
                    "supabase": settings.use_supabase
                }
            }
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Status check failed"
        )


# =============================================================================
# DEVELOPMENT ENDPOINTS
# =============================================================================

if settings.is_development:

    @app.get("/debug/config", tags=["Debug"])
    async def debug_config():
        """Debug endpoint to view configuration (development only)."""
        from src.core.config import validate_configuration
        return {
            "success": True,
            "data": validate_configuration()
        }

    @app.get("/debug/database", tags=["Debug"])
    async def debug_database():
        """Debug endpoint for database information (development only)."""
        from src.core.database import get_database_info, get_table_stats

        try:
            db_info = await get_database_info()
            table_stats = await get_table_stats()

            return {
                "success": True,
                "data": {
                    "database_info": db_info,
                    "table_stats": table_stats
                }
            }
        except Exception as e:
            logger.error(f"Debug database failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database debug failed"
            )

    @app.post("/debug/test-telegram", tags=["Debug"])
    async def debug_test_telegram():
        """Debug endpoint to test Telegram connection (development only)."""
        try:
            telegram_service = await get_telegram_service()
            health_check = await telegram_service.health_check()

            # Test sending a message
            test_message = f"🧪 Test message from Telegram Assistant\n\nTime: {health_check['timestamp']}\nStatus: {health_check['status']}"

            result = await telegram_service.send_message(test_message)

            return {
                "success": True,
                "data": {
                    "health_check": health_check,
                    "test_message_result": result,
                    "message": "Telegram test completed successfully"
                }
            }
        except Exception as e:
            logger.error(f"Telegram test failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )


# =============================================================================
# API ROUTES (Will be expanded in next phases)
# =============================================================================

# Import and include Telegram webhook endpoints
from fastapi import Request, BackgroundTasks
from src.services.telegram_service import get_telegram_service
from src.workflows.telegram_handler import telegram_message_handler


@app.post("/api/telegram-webhook", tags=["Telegram"])
async def telegram_webhook_endpoint(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Telegram webhook updates."""
    import json

    try:
        # Parse JSON body
        body = await request.body()
        if not body:
            logger.warning("Empty webhook body received")
            return {"status": "error", "message": "Empty body"}

        try:
            update = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook: {e}")
            return {"status": "error", "message": "Invalid JSON"}

        # Log the update
        logger.info("Received Telegram webhook", extra={
            "update_id": update.get("update_id"),
            "has_message": "message" in update,
            "has_callback_query": "callback_query" in update
        })

        # Validate update structure
        if "update_id" not in update:
            logger.warning("Invalid update structure - missing update_id")
            return {"status": "error", "message": "Invalid update"}

        # Process update in background
        background_tasks.add_task(telegram_message_handler.handle_update, update)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {e}")
        return {"status": "error", "message": "Internal server error"}


@app.get("/api/telegram-webhook", tags=["Telegram"])
async def get_webhook_info():
    """Get webhook information."""
    try:
        telegram_service = await get_telegram_service()
        webhook_info = await telegram_service.get_webhook_info()

        return {
            "success": True,
            "data": webhook_info.get("result", {})
        }
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/telegram-webhook/setup", tags=["Telegram"])
async def setup_telegram_webhook():
    """Setup Telegram webhook URL."""
    try:
        telegram_service = await get_telegram_service()
        webhook_url = settings.telegram_webhook_url

        if not webhook_url or "your-app-domain" in webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook URL not configured"
            )

        result = await telegram_service.set_webhook(webhook_url)

        logger.info(f"Webhook setup completed", extra={
            "webhook_url": webhook_url
        })

        return {
            "success": True,
            "data": {
                "webhook_url": webhook_url,
                "result": result.get("result", {})
            }
        }

    except Exception as e:
        logger.error(f"Error setting up webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/api/telegram-webhook", tags=["Telegram"])
async def delete_telegram_webhook():
    """Delete Telegram webhook."""
    try:
        telegram_service = await get_telegram_service()
        result = await telegram_service.delete_webhook()

        logger.info("Webhook deleted")

        return {
            "success": True,
            "data": result.get("result", {})
        }

    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =============================================================================
# DEVELOPMENT SERVER
# =============================================================================

if __name__ == "__main__":
    logger.info("Starting development server...")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
        access_log=settings.is_development
    )