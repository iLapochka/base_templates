"""Contract: specs/contract/shared/operator-admin.md."""

import time
from collections.abc import AsyncIterator
from pathlib import Path
from secrets import token_urlsafe

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.config import config
from core.database import Database
from src.shared.presentation.admin import (
    ADMIN_SESSION_LIFETIME_SECONDS,
    OperatorCredentials,
    mount_admin,
)

OPERATOR_USERNAME = 'operator'
ADMIN_INDEX = '/admin/'


@pytest.fixture
def operator_password() -> str:
    # Made up at run time, so no secret scanner mistakes a fixture for a leaked credential.
    return token_urlsafe()


@pytest.fixture
async def admin_database(tmp_path: Path) -> AsyncIterator[Database]:
    admin_database = Database(database_url=f'sqlite+aiosqlite:///{tmp_path / "admin.db"}', echo=False)
    yield admin_database
    await admin_database.engine.dispose()


def build_app(
    *,
    admin_database: Database,
    password: str,
    secret_key: str,
    https_only: bool = False,
) -> FastAPI:
    app = FastAPI()
    mount_admin(
        app=app,
        session_factory=admin_database.session_factory,
        operator_credentials=OperatorCredentials(
            username=OPERATOR_USERNAME,
            password=password,
            secret_key=secret_key,
        ),
        model_views=[],
        https_only=https_only,
    )
    return app


@pytest.fixture
async def admin_client(
    admin_database: Database,
    operator_password: str,
) -> AsyncIterator[AsyncClient]:
    app = build_app(
        admin_database=admin_database,
        password=operator_password,
        secret_key=token_urlsafe(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client


async def sign_in(*, admin_client: AsyncClient, username: str, password: str) -> None:
    await admin_client.post('/admin/login', data={'username': username, 'password': password})


async def is_signed_in(*, admin_client: AsyncClient) -> bool:
    return (await admin_client.get(ADMIN_INDEX)).status_code == 200


async def test_sends_a_visitor_with_no_session_to_the_sign_in_page(
    admin_client: AsyncClient,
) -> None:
    """The admin is closed until an operator has signed in."""
    response = await admin_client.get(ADMIN_INDEX)

    assert response.status_code == 302
    assert response.headers['location'].endswith('/admin/login')


@pytest.mark.parametrize('https_only', [False, True])
async def test_keeps_the_sign_in_for_the_browser_session_only(
    admin_database: Database,
    operator_password: str,
    https_only: bool,
) -> None:
    """An operator signs in with the admin credentials: the cookie ends with the browser."""
    app = build_app(
        admin_database=admin_database,
        password=operator_password,
        secret_key=token_urlsafe(),
        https_only=https_only,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        sign_in_response = await client.post(
            '/admin/login',
            data={'username': OPERATOR_USERNAME, 'password': operator_password},
        )
        assert await is_signed_in(admin_client=client) is not https_only

    session_cookie = sign_in_response.headers['set-cookie'].lower()
    assert 'max-age' not in session_cookie
    assert 'expires' not in session_cookie
    assert ('secure' in session_cookie) is https_only


@pytest.mark.parametrize(
    ('username', 'password_kind'),
    [
        ('somebody-else', 'correct'),
        (OPERATOR_USERNAME, 'wrong'),
        (OPERATOR_USERNAME, 'empty'),
        ('', 'correct'),
    ],
)
async def test_refuses_wrong_credentials_without_saying_which_was_wrong(
    admin_client: AsyncClient,
    operator_password: str,
    username: str,
    password_kind: str,
) -> None:
    """Wrong credentials are refused."""
    password = {'correct': operator_password, 'wrong': token_urlsafe(), 'empty': ''}[password_kind]

    refusal = await admin_client.post(
        '/admin/login',
        data={'username': username, 'password': password},
    )

    assert not await is_signed_in(admin_client=admin_client)
    assert 'Invalid credentials.' in refusal.text


async def test_refuses_the_api_key_as_an_admin_password(admin_client: AsyncClient) -> None:
    """The API key is not an admin credential."""
    await sign_in(admin_client=admin_client, username=OPERATOR_USERNAME, password=config.API_KEY)

    assert not await is_signed_in(admin_client=admin_client)


@pytest.mark.parametrize(('password', 'secret_key'), [('', 'a-secret'), ('a-password', '')])
async def test_serves_no_admin_without_a_password_and_a_secret(
    admin_database: Database,
    password: str,
    secret_key: str,
) -> None:
    """Without a configured password there is no admin at all."""
    app = build_app(admin_database=admin_database, password=password, secret_key=secret_key)

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/admin/login')

    assert response.status_code == 404


async def test_signing_out_ends_the_session_at_once(
    admin_client: AsyncClient,
    operator_password: str,
) -> None:
    """Signing out ends the session at once."""
    await sign_in(admin_client=admin_client, username=OPERATOR_USERNAME, password=operator_password)
    assert await is_signed_in(admin_client=admin_client)

    await admin_client.get('/admin/logout')

    assert not await is_signed_in(admin_client=admin_client)


async def test_a_sign_in_expires_on_the_server_even_if_the_cookie_is_kept(
    admin_client: AsyncClient,
    operator_password: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sign-in lasts at most the admin session lifetime, whatever the browser keeps."""
    await sign_in(admin_client=admin_client, username=OPERATOR_USERNAME, password=operator_password)
    signed_in_at = time.time()

    monkeypatch.setattr(time, 'time', lambda: signed_in_at + ADMIN_SESSION_LIFETIME_SECONDS - 60)
    assert await is_signed_in(admin_client=admin_client)

    monkeypatch.setattr(time, 'time', lambda: signed_in_at + ADMIN_SESSION_LIFETIME_SECONDS + 60)
    assert not await is_signed_in(admin_client=admin_client)
