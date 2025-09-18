"""
Main API endpoint for Vercel serverless deployment.
This serves as the entry point for the Telegram Assistant API.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mangum import Mangum
import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Create a simple FastAPI app for testing
app = FastAPI(title="Telegram Assistant API")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "success": True,
        "message": "Telegram Assistant API is running",
        "status": "healthy"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "success": True,
        "status": "healthy",
        "message": "API is operational"
    }

# Create Mangum handler for serverless deployment
handler = Mangum(app, lifespan="off")