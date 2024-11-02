# web.py

from fastapi import FastAPI, WebSocket, BackgroundTasks, Request  # Add Request import
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from pathlib import Path
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Download Manager")

# Ensure directories exist
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create directories if they don't exist
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):  # Add request parameter
    """Serve main page"""
    try:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,  # Pass request to template
                "base_url": str(request.base_url)
            }
        )
    except Exception as e:
        logger.error(f"Failed to serve index page: {e}")
        return {"error": str(e)}

@app.get("/status")
async def get_status(request: Request):
    """Get download status"""
    return {
        "status": "ok",
        "downloads": []  # Add your download list here
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Handle websocket data
            await websocket.send_json({"status": "received", "data": data})
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

if __name__ == "__main__":
    try:
        logger.info("Starting Download Manager Web Interface")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
