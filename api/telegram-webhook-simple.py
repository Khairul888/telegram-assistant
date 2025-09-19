"""
Simplified Vercel serverless function for handling Telegram webhook.
Minimal dependencies approach for debugging.
"""

import json
import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

# Create FastAPI app for this endpoint
app = FastAPI(title="Telegram Webhook Simple")

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
        except json.JSONDecodeError as e:
            return JSONResponse({"status": "error", "message": f"Invalid JSON: {e}"}, status_code=400)

        # Extract message info
        message_info = extract_message_info(update)

        if message_info:
            # Send a simple response back to the user
            await send_simple_response(message_info)

        return JSONResponse({
            "status": "ok",
            "message": "Update processed successfully",
            "update_id": update.get("update_id"),
            "message_info": message_info
        })

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": f"Processing error: {str(e)}",
            "error_type": type(e).__name__
        }, status_code=500)

@app.get("/")
async def webhook_info():
    """Get webhook information."""
    return JSONResponse({
        "status": "ok",
        "message": "Telegram webhook endpoint (simple version) is operational",
        "endpoint": "/api/telegram-webhook-simple"
    })

def extract_message_info(update):
    """Extract basic message information from update."""
    try:
        if "message" in update:
            message = update["message"]

            # Extract basic info
            chat_id = message["chat"]["id"]
            message_id = message["message_id"]

            # Extract user info
            user = message.get("from", {})
            user_id = user.get("id")
            first_name = user.get("first_name", "")

            # Extract message content
            content = ""
            if "text" in message:
                content = message["text"]
            elif "caption" in message:
                content = message["caption"]
            elif "document" in message:
                content = f"[Document: {message['document'].get('file_name', 'Unknown')}]"
            elif "photo" in message:
                content = "[Photo]"
            else:
                content = "[Other message type]"

            return {
                "chat_id": chat_id,
                "message_id": message_id,
                "user_id": user_id,
                "first_name": first_name,
                "content": content
            }
    except Exception as e:
        print(f"Error extracting message info: {e}")

    return None

async def send_simple_response(message_info):
    """Send a simple response back to the user."""
    try:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            print("No bot token found")
            return

        chat_id = message_info["chat_id"]
        user_content = message_info["content"]
        first_name = message_info.get("first_name", "there")

        # Determine response
        if user_content.lower().startswith('/start'):
            response_text = f"🤖 Hello {first_name}! I'm your AI Document Assistant.\n\nI'm working on processing your messages! Try sending me any text and I'll respond."
        elif user_content.lower().startswith('/help'):
            response_text = "📋 Available commands:\n/start - Get started\n/help - Show this help\n/status - Check status\n\nYou can also send me any message and I'll respond!"
        elif user_content.lower().startswith('/status'):
            response_text = "✅ Bot is online and working!\n🔧 Status: Operational\n📡 Connection: Good"
        else:
            response_text = f"📩 Hi {first_name}! I received your message: \"{user_content}\"\n\n🤖 I'm an AI assistant that helps with document processing and analysis. I'm currently in simple mode while we work on the full features!"

        # Send response
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": response_text,
            "parse_mode": "Markdown"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            if response.status_code == 200:
                print(f"Response sent successfully to {chat_id}")
            else:
                print(f"Failed to send response: {response.status_code}")

    except Exception as e:
        print(f"Error sending response: {e}")

# Create Mangum handler for serverless deployment
handler = Mangum(app, lifespan="off")