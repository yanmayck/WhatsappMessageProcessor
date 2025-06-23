import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # For CORS if needed
from config import Config
from database_session import create_db_tables, get_db # Import from new file

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

def create_app():
    app = FastAPI(
        title="WhatsApp Message Processor API",
        description="API for processing WhatsApp messages and interacting with AI/CRM.",
        version="1.0.0",
    )

    # CORS middleware (adjust origins as needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    # Register routers here
    from routes.webhook import router as webhook_router
    # from routes.dashboard import dashboard_bp # To be converted
    # from routes.tasks import tasks_bp # To be converted

    app.include_router(webhook_router, prefix="/webhook")
    # app.include_router(dashboard_router, prefix="/dashboard") # Once converted
    # app.include_router(tasks_router, prefix="/tasks") # Once converted

    @app.on_event("startup")
    async def startup_event():
        """Create database tables on application startup."""
        create_db_tables()
        logging.info("Database tables checked/created.")

    return app

app = create_app()

# To run locally with uvicorn: uvicorn app:app --reload --port 8080
# The if __name__ == '__main__' block is generally not used with uvicorn directly
# as uvicorn loads the 'app' object directly.
