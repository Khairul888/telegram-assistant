"""
Vercel serverless function for handling Telegram webhook.
"""

import json
import os
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

# Add the project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import the telegram message handler
from src.workflows.telegram_handler import telegram_message_handler
from src.core.logger import get_logger

logger = get_logger(__name__)

# Create FastAPI app for this endpoint
app = FastAPI(title="Telegram Webhook")

@app.post("/")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram webhook updates."""
    try:
        # Parse JSON body
        body = await request.body()
        if not body:
            logger.warning("Received empty webhook body")
            return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)

        try:
            update = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook: {e}")
            return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

        logger.info(f"Received Telegram update: {update.get('update_id', 'unknown')}")

        # Process the update using the telegram message handler
        await telegram_message_handler.handle_update(update)

        return JSONResponse({"status": "ok", "message": "Update processed successfully"})

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/")
async def webhook_info():
    """Get webhook information."""
    return JSONResponse({
        "status": "ok",
        "message": "Telegram webhook endpoint is operational",
        "endpoint": "/api/telegram-webhook"
    })

# Create Mangum handler for serverless deployment
handler = Mangum(app, lifespan="off")