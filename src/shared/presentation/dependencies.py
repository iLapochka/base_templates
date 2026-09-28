import secrets
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config
from core.database import get_session
from src.shared.domain.event_bus import EventBus
from src.shared.domain.unit_of_work import UnitOfWork
from src.shared.exceptions import UnauthorizedError
from src.shared.infrastructure.event_bus import InProcessEventBus
from src.shared.infrastructure.unit_of_work import SQLAlchemyUnitOfWork

# Wiring every bounded context builds its own use cases on top of; nothing here knows a context.

API_KEY_HEADER = 'X-API-Key'

SessionDep = Annotated[AsyncSession, Depends(get_session)]
# One bus for the process: subscriptions are made once, at startup, in `src/main.py`.
event_bus = InProcessEventBus()


def get_unit_of_work(session: SessionDep) -> UnitOfWork:
    """The transaction boundary for this request, for the caller to run work inside."""
    return SQLAlchemyUnitOfWork(session)


async def verify_api_key(
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Refuse every caller that does not present the server's key, in constant time."""
    if api_key is None or not secrets.compare_digest(api_key.encode(), config.API_KEY.encode()):
        raise UnauthorizedError


def get_event_bus() -> EventBus:
    """The bus every context publishes to and nobody owns."""
    return event_bus


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]

ApiKeyDep = Depends(verify_api_key)

EventBusDep = Annotated[EventBus, Depends(get_event_bus)]
