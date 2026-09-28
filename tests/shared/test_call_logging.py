import logging
from dataclasses import dataclass, field
from secrets import token_urlsafe

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.call_logging import log_call


@dataclass(frozen=True, slots=True)
class SourceCookies:
    site: str
    session_token: str = field(repr=False)


class VideoDownloader:
    @log_call
    async def download_video(self, *, url: str, cookies: SourceCookies) -> str:
        return 'downloaded'


async def test_logs_the_class_the_method_and_every_argument_but_a_credential(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A call is logged as Class.method(name=value), with no credential in it."""
    # Made up at run time, so no secret scanner mistakes a fixture for a leaked credential.
    session_token = token_urlsafe()
    cookies = SourceCookies(site='example.com', session_token=session_token)

    with caplog.at_level(logging.INFO, logger='video_helper.calls'):
        answer = await VideoDownloader().download_video(
            url='https://example.com/v/1',
            cookies=cookies,
        )

    assert answer == 'downloaded'
    assert caplog.messages == [
        "VideoDownloader.download_video(url='https://example.com/v/1', "
        "cookies=SourceCookies(site='example.com'))",
    ]
    assert session_token not in caplog.text


async def test_health_answers_without_an_api_key() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
