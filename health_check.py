"""
Health Check Handler for Railway Deployment
Add this to your aiohttp application for better monitoring
"""

from aiohttp import web
import time
import os


# Store bot start time
_start_time = time.time()


async def health_handler(request):
    """
    Health check endpoint for Railway monitoring
    Returns bot status and uptime
    """
    uptime_seconds = int(time.time() - _start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    health_data = {
        "status": "healthy",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_seconds,
        "runtime_environment": os.getenv("RUNTIME_ENVIRONMENT", "PROD"),
        "timestamp": int(time.time())
    }
    
    return web.json_response(health_data)


async def root_handler(request):
    """
    Root endpoint - returns basic bot info
    """
    return web.json_response({
        "bot": "AiogramShopBot",
        "status": "running",
        "version": "1.0.0",
        "deployment": "Railway"
    })


def setup_health_routes(app: web.Application):
    """
    Setup health check and root routes
    Call this function in your run.py:
    
    from health_check import setup_health_routes
    setup_health_routes(app)
    """
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", root_handler)
    
    return app


# ============================================
# USAGE IN run.py:
# ============================================
"""
# Add to your run.py after creating the app:

from aiohttp import web
from health_check import setup_health_routes

app = web.Application()

# Setup webhook handler
webhook_requests_handler.register(app, path=webhook_path)

# ADD THIS LINE:
setup_health_routes(app)

# Setup application
setup_application(app, dp, bot=bot)
"""
