from dataclasses import dataclass, field
from uuid import UUID, uuid4


# Every subclass repeats `eq=False`: a plain `@dataclass` regenerates `__eq__` over all fields.
@dataclass(kw_only=True, eq=False)
class BaseEntity:
    """Identity, not value: two entities are the same when their ids match."""

    id: UUID = field(default_factory=uuid4)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))
