from fastapi import APIRouter, FastAPI

from core.config import config
from core.database import database
from src.shared.presentation.admin import OperatorCredentials, mount_admin
from src.shared.presentation.dependencies import ApiKeyDep
from src.shared.presentation.exception_handlers import register_exception_handlers
from src.shared.presentation.middleware import LogContextMiddleware

# The schema maps every route; outside local it is not served, so only `/health` stays open.
app = FastAPI(
    title='Video Helper',
    docs_url='/api/docs' if config.is_local else None,
    redoc_url='/api/redoc' if config.is_local else None,
    openapi_url='/openapi.json' if config.is_local else None,
)
app.add_middleware(LogContextMiddleware)
register_exception_handlers(app)

# The key guards everything mounted here; `/health` sits outside and stays open.
api_router = APIRouter(prefix='/api/v1', dependencies=[ApiKeyDep])
# Context routers go here: `app.include_router` below copies the routes it sees at that moment.
app.include_router(api_router)

mount_admin(
    app=app,
    session_factory=database.session_factory,
    operator_credentials=OperatorCredentials(
        username=config.ADMIN_USERNAME,
        password=config.ADMIN_PASSWORD,
        secret_key=config.ADMIN_SECRET_KEY,
    ),
    # Each context's views from `src/<context>/presentation/admin.py` go here.
    model_views=[],
    https_only=not config.is_local,
)


@app.get('/health', tags=['health'])
async def health() -> dict[str, str]:
    """Liveness only — the one route that carries no API key."""
    return {'status': 'ok'}
