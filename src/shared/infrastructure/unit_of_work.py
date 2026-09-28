from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.domain.unit_of_work import UnitOfWork


class SQLAlchemyUnitOfWork(UnitOfWork):
    """Adapts one session to the transaction port; a failed block leaves the session usable."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
