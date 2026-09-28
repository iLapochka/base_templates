import asyncio
import logging
from typing import Any

from src.shared.domain.event_bus import EventBus, EventHandler
from src.shared.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class InProcessEventBus(EventBus):
    """Delivers events to handlers running in this process, each on its own task."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler[Any]]] = {}
        # A task nobody holds is a task the garbage collector may cancel mid-run.
        self._running_handlers: set[asyncio.Task[None]] = set()

    def subscribe[EventT: DomainEvent](
        self,
        *,
        event_type: type[EventT],
        handler: EventHandler[EventT],
    ) -> None:
        """Register the handler; every later event of this type reaches it."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, *, event: DomainEvent) -> None:
        """Hand the event to each handler and return — the publisher waits for none of them."""
        for handler in self._handlers.get(type(event), []):
            task = asyncio.create_task(self._deliver(handler=handler, event=event))
            self._running_handlers.add(task)
            task.add_done_callback(self._running_handlers.discard)

    @staticmethod
    async def _deliver(*, handler: EventHandler[Any], event: DomainEvent) -> None:
        """One delivery; a handler that raises is logged here, where somebody can see it."""
        try:
            await handler(event)
        except Exception:  # pylint: disable=broad-exception-caught
            # Nothing awaits this task, so an escaping exception would be a silent one.
            logger.exception('Handler failed for %s', type(event).__name__)
