from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.bot.core.config import ConfigManager


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from src.web.routes.ws import broadcast_config_change

    cm: ConfigManager | None = app.state.config_manager
    if cm is not None:
        cm.on_change(broadcast_config_change)
    yield


def create_app(config_manager: ConfigManager | None = None, bot: Any = None) -> FastAPI:
    app = FastAPI(title="Ressy Bot Dashboard", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config_manager = config_manager
    app.state.bot = bot

    from src.web.routes.config import router as config_router
    from src.web.routes.ws import router as ws_router
    from src.web.routes.activity import router as activity_router, get_log

    app.include_router(config_router, prefix="/api")
    app.include_router(activity_router, prefix="/api")
    app.include_router(ws_router)

    # Pre-create the activity log singleton so plugins can push events
    get_log(app)

    return app


def mount_static_files(app: FastAPI) -> None:
    """Mount static files as a catch-all fallback.

    Must be called *after* all API routes and plugin routers are registered,
    otherwise the static mount (at "/") would shadow every later route.
    """
    import os

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
