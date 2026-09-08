from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_data, routes_health, routes_profile, routes_scenarios, routes_sessions, ws_conversation
from app.config import get_settings
from app.db.session import init_db
from app.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="LinguSim API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_scenarios.router)
app.include_router(routes_profile.router)
app.include_router(routes_sessions.router)
app.include_router(routes_data.router)
app.include_router(ws_conversation.router)
