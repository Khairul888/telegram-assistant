"""
Main API endpoint for Vercel serverless deployment.
This serves as the entry point for the Telegram Assistant API.
"""

from fastapi import FastAPI
from mangum import Mangum
import os
import sys

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Create Mangum handler for serverless deployment
handler = Mangum(app, lifespan="off")

# Export for Vercel
def handler_func(event, context):
    """Vercel serverless function handler."""
    return handler(event, context)