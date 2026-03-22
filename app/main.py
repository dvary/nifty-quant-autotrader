import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load environment variables FIRST before other imports
load_dotenv()

from app.core.database import engine as db_engine, Base
from app.core.logger import logger
from app.api.endpoints import router as api_router

def create_app():
    # Initialize database tables
    Base.metadata.create_all(bind=db_engine)
    logger.info("Database tables initialized.")

    app = FastAPI(title="Zerodha 44 MA Trading Bot")

    # Include API router
    app.include_router(api_router, prefix="/api")

    # Mount static dashboard route
    app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")

    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting Trading Bot Application...")
        # Here we will later initialize the WebSocket and Trading Engine

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down Trading Bot Application...")
        # Cleanup connections here

    @app.get("/api/status")
    async def get_status():
        return {"status": "running"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
