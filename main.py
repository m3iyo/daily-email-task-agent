import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api_routes import api_router
from app_state import build_app_services
from config import settings
from db.database import create_tables
from ui_routes import build_ui_router

PROJECT_ROOT = Path(__file__).resolve().parent

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Daily Email & Task Agent API",
        description="API-first email processing and task automation service with optional demo UI.",
        version="1.1.0",
    )

    app.state.services = build_app_services()

    if settings.enable_ui:
        app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")
        templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
        app.include_router(build_ui_router(templates))

    app.include_router(api_router)

    @app.on_event("startup")
    async def startup_event():
        create_tables()
        if settings.enable_scheduler:
            app.state.services.scheduler.start()
            logger.info("Scheduler enabled on startup")
        else:
            logger.info("Scheduler disabled by configuration")
        logger.info("Application started successfully")

    @app.on_event("shutdown")
    async def shutdown_event():
        if settings.enable_scheduler:
            app.state.services.scheduler.stop()
        logger.info("Application shutdown complete")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
