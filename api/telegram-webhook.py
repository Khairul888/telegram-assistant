"""
Vercel serverless function for handling Telegram webhook.
"""

import json
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# Import the main app to handle the webhook
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.telegram_service import get_telegram_service
from src.workflows.telegram_handler import TelegramMessageHandler
from src.core.logger import get_logger
from src.core.database import get_database_session

logger = get_logger(__name__)

# Create FastAPI app for this endpoint
app = FastAPI(title="Telegram Webhook")

# Initialize handler
telegram_handler = TelegramMessageHandler()


async def process_update_background(update: Dict[str, Any]):
    """Process Telegram update in background."""
    try:
        await telegram_handler.handle_update(update)
    except Exception as e:
        logger.error(f"Error processing Telegram update in background: {e}", extra={
            "update": update
        })


@app.post("/api/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Telegram webhook updates."""
    try:
        # Parse JSON body
        body = await request.body()
        if not body:
            logger.warning("Empty webhook body received")
            return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)

        try:
            update = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook: {e}")
            return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

        # Log the update (but mask sensitive data)
        logger.info("Received Telegram webhook", extra={
            "update_id": update.get("update_id"),
            "has_message": "message" in update,
            "has_callback_query": "callback_query" in update
        })

        # Validate update structure
        if "update_id" not in update:
            logger.warning("Invalid update structure - missing update_id")
            return JSONResponse({"status": "error", "message": "Invalid update"}, status_code=400)

        # Process update in background to respond quickly to Telegram
        background_tasks.add_task(process_update_background, update)

        # Return success immediately
        return JSONResponse({"status": "ok"})

    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {e}")
        return JSONResponse(
            {"status": "error", "message": "Internal server error"},
            status_code=500
        )


@app.get("/api/telegram-webhook")
async def webhook_info():
    """Get webhook information (for debugging)."""
    try:
        telegram_service = await get_telegram_service()
        webhook_info = await telegram_service.get_webhook_info()

        return JSONResponse({
            "status": "ok",
            "webhook_info": webhook_info.get("result", {}),
            "timestamp": webhook_info.get("timestamp")
        })
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/api/telegram-webhook/setup")
async def setup_webhook():
    """Setup webhook URL (for deployment)."""
    try:
        telegram_service = await get_telegram_service()

        # Use the URL from environment
        from src.core.config import settings
        webhook_url = settings.telegram_webhook_url

        if not webhook_url or "your-app-domain" in webhook_url:
            return JSONResponse(
                {"status": "error", "message": "Webhook URL not configured"},
                status_code=400
            )

        result = await telegram_service.set_webhook(webhook_url)

        logger.info(f"Webhook setup completed", extra={
            "webhook_url": webhook_url,
            "result": result
        })

        return JSONResponse({
            "status": "ok",
            "webhook_url": webhook_url,
            "result": result.get("result", {})
        })

    except Exception as e:
        logger.error(f"Error setting up webhook: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.delete("/api/telegram-webhook")
async def delete_webhook():
    """Delete webhook (switch to polling mode)."""
    try:
        telegram_service = await get_telegram_service()
        result = await telegram_service.delete_webhook()

        logger.info("Webhook deleted")

        return JSONResponse({
            "status": "ok",
            "result": result.get("result", {})
        })

    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.get("/api/telegram-webhook/health")
async def webhook_health():
    """Health check for webhook endpoint."""
    try:
        telegram_service = await get_telegram_service()
        health = await telegram_service.health_check()

        return JSONResponse({
            "status": "ok",
            "telegram_health": health,
            "webhook_endpoint": "operational"
        })

    except Exception as e:
        logger.error(f"Webhook health check failed: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


# For Vercel deployment
def handler(request, context):
    """Vercel handler function."""
    import uvicorn
    return uvicorn.run(app, host="0.0.0.0", port=8000)