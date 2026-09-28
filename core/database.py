from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import config


class Database:
    """Async engine and session factory for one database URL."""

    def __init__(self, *, database_url: str, echo: bool) -> None:
        self.engine = create_async_engine(database_url, echo=echo)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """FastAPI dependency that yields a transactional async session."""
        async with self.session_factory() as session:
            yield session


database = Database(database_url=config.DATABASE_URL, echo=config.is_local)
get_session = database.get_session
