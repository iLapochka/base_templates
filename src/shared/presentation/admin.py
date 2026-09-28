import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

# The one key the session carries: when the operator signed in, in epoch seconds.
SIGNED_IN_AT_SESSION_KEY = 'operator_signed_in_at'
# The signed cookie itself never expires, so a copied one stops working after this.
ADMIN_SESSION_LIFETIME_SECONDS = 12 * 60 * 60


@dataclass(frozen=True, slots=True)
class OperatorCredentials:
    """The one operator of `/admin`, and the secret its session cookie is signed with."""

    username: str
    password: str = field(repr=False)
    secret_key: str = field(repr=False)

    @property
    def is_configured(self) -> bool:
        """A default password is one everybody knows, so an empty one opens nothing."""
        return bool(self.password and self.secret_key)


class OperatorAuthentication(AuthenticationBackend):
    """Lets in only the one operator whose credentials the server was started with."""

    def __init__(self, *, operator_credentials: OperatorCredentials, https_only: bool) -> None:
        # No max_age: the cookie ends with the browser session instead of Starlette's 14 days.
        super().__init__(
            secret_key=operator_credentials.secret_key,
            max_age=None,
            https_only=https_only,
        )
        self._operator_credentials = operator_credentials

    async def login(self, request: Request) -> bool:
        """Sign in on an exact username and password; both are compared in constant time."""
        form = await request.form()
        is_username_correct = secrets.compare_digest(
            str(form.get('username', '')).encode(),
            self._operator_credentials.username.encode(),
        )
        is_password_correct = secrets.compare_digest(
            str(form.get('password', '')).encode(),
            self._operator_credentials.password.encode(),
        )
        # Both are always compared, so the timing never says which of the two was wrong.
        if not (is_username_correct and is_password_correct):
            return False
        request.session[SIGNED_IN_AT_SESSION_KEY] = int(time.time())
        return True

    async def logout(self, request: Request) -> bool:
        """End the session at once."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Whether this browser session belongs to an operator who signed in recently enough."""
        signed_in_at = request.session.get(SIGNED_IN_AT_SESSION_KEY)
        if not isinstance(signed_in_at, int):
            return False
        if time.time() - signed_in_at > ADMIN_SESSION_LIFETIME_SECONDS:
            request.session.clear()
            return False
        return True


def mount_admin(
    *,
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    operator_credentials: OperatorCredentials,
    model_views: Sequence[type[ModelView]],
    https_only: bool,
) -> None:
    """Serve `/admin` over these views, or nothing at all without configured credentials."""
    # An admin that is not mounted answers 404 and cannot be signed in to.
    if not operator_credentials.is_configured:
        return
    admin = Admin(
        app,
        session_maker=session_factory,
        title='Video Helper',
        authentication_backend=OperatorAuthentication(
            operator_credentials=operator_credentials,
            https_only=https_only,
        ),
    )
    for model_view in model_views:
        admin.add_view(model_view)
