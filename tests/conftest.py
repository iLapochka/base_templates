import pytest

from src.main import app
from src.shared.domain.event_bus import EventBus, EventHandler
from src.shared.domain.events import DomainEvent
from src.shared.presentation.dependencies import get_event_bus


class RecordingEventBus(EventBus):
    """Keeps what was announced instead of delivering it, so no test starts a render."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def subscribe[EventT: DomainEvent](
        self,
        *,
        event_type: type[EventT],
        handler: EventHandler[EventT],
    ) -> None:
        """Accepted and ignored: a test asserts on what was published, not on who listens."""

    async def publish(self, *, event: DomainEvent) -> None:
        self.published.append(event)


@pytest.fixture
def event_bus() -> RecordingEventBus:
    return RecordingEventBus()


@pytest.fixture(autouse=True)
def _bus_that_runs_nothing(event_bus: RecordingEventBus) -> None:
    """Every test publishes into the recorder, never into the bus that drives ffmpeg."""
    app.dependency_overrides[get_event_bus] = lambda: event_bus
