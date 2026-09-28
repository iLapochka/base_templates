from dataclasses import dataclass

# The whole language two contexts share. Neither imports the other; both know these.


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Something that has already happened, announced to whoever cares."""
