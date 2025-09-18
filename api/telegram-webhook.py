"""
Vercel serverless function for handling Telegram webhook.
"""

import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

# Create FastAPI app for this endpoint
app = FastAPI(title="Telegram Webhook")

@app.post("/")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram webhook updates."""
    try:
        # Parse JSON body
        body = await request.body()
        if not body:
            return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)

        try:
            update = json.loads(body)
        except json.JSONDecodeError:
            return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

        # Simple response for now - just acknowledge receipt
        return JSONResponse({"status": "ok", "message": "Webhook received"})

    except Exception as e:
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