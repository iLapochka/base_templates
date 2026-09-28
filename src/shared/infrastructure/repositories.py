from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import ColumnElement, delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.infrastructure.models import BaseModel

# One row's condition, the only SQL a context's repository ever writes: `UserModel.id == user_id`.
type Condition = ColumnElement[bool]


class SQLAlchemyRepository[ModelT: BaseModel]:
    """The query shapes every table needs, so no context's repository builds a statement itself."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_row(self, *, model: ModelT) -> None:
        """Hold a new row for the transaction the caller commits."""
        self._session.add(model)

    async def find_row(self, *, where: Collection[Condition]) -> ModelT | None:
        """The row matching every condition, or nothing."""
        row: ModelT | None = await self._session.scalar(select(self.model).where(*where))
        return row

    async def find_rows(self, *, order_by: Collection[Any]) -> Sequence[ModelT]:
        """Every row of this table, in the order asked for."""
        rows = await self._session.scalars(select(self.model).order_by(*order_by))
        return rows.all()

    async def row_exists(self, *, where: Collection[Condition]) -> bool:
        """Whether any row matches; the database answers without a row being read back."""
        return bool(await self._session.scalar(select(exists().where(*where))))

    async def update_rows(self, *, where: Collection[Condition], values: dict[str, Any]) -> None:
        """Stage the new column values on every matching row."""
        await self._session.execute(update(self.model).where(*where).values(**values))

    async def delete_rows(self, *, where: Collection[Condition]) -> None:
        """Stage the removal of every matching row."""
        await self._session.execute(delete(self.model).where(*where))
