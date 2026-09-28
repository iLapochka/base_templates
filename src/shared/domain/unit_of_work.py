from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class UnitOfWork(ABC):
    """The transaction boundary: what is staged inside the block commits whole, or not at all."""

    async def __aenter__(self) -> Self:
        """Open the block work is staged in."""
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Commit what the block staged, or roll it back so the next block starts clean."""
        if exception_type is not None:
            await self.rollback()
            return
        try:
            await self.commit()
        except BaseException:
            # A failed commit leaves the session unusable until it is rolled back.
            await self.rollback()
            raise

    @abstractmethod
    async def commit(self) -> None:
        """Make every change staged so far durable."""

    @abstractmethod
    async def rollback(self) -> None:
        """Discard every change staged so far."""
