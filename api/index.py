"""
Vercel Python Serverless — FastAPI adapter
Vercel expects a handler at api/index.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

# Vercel uses this as the ASGI handler
handler = app
