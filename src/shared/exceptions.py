from http import HTTPStatus
from typing import ClassVar


class BaseDomainException(Exception):  # noqa: N818
    """Root of every failure the hexagon reports outward."""

    # `code` is branched on, `message` is shown, `status_code` is what the API answers with.
    code: ClassVar[str] = 'domain_error'
    message: ClassVar[str] = 'The request could not be completed.'
    status_code: ClassVar[int] = HTTPStatus.BAD_REQUEST

    def __init__(self) -> None:
        super().__init__(self.message)


class UnauthorizedError(BaseDomainException):
    """The caller presented no credential, or one that does not match."""

    code: ClassVar[str] = 'unauthorized'
    message: ClassVar[str] = 'Missing or invalid API key.'
    status_code: ClassVar[int] = HTTPStatus.UNAUTHORIZED


class ServiceUnavailableError(BaseDomainException):
    """A dependency the request needed is down; the caller may retry."""

    code: ClassVar[str] = 'service_unavailable'
    message: ClassVar[str] = 'The service is temporarily unavailable. Please retry.'
    status_code: ClassVar[int] = HTTPStatus.SERVICE_UNAVAILABLE
