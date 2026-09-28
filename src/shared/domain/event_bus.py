from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from src.shared.domain.events import DomainEvent

# A handler is given its own event and nothing else; whatever it needs, it resolves for itself.
type EventHandler[HandledEventT: DomainEvent] = Callable[[HandledEventT], Awaitable[None]]


class EventBus(ABC):
    """Where a context announces what happened, without knowing who listens."""

    @abstractmethod
    def subscribe[EventT: DomainEvent](
        self,
        *,
        event_type: type[EventT],
        handler: EventHandler[EventT],
    ) -> None:
        """Ask to be told about every event of this type from now on."""

    @abstractmethod
    async def publish(self, *, event: DomainEvent) -> None:
        """Announce the event; the publisher never waits for a handler and never sees it fail."""
