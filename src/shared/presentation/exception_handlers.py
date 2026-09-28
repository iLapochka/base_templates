import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from src.shared.exceptions import BaseDomainException, ServiceUnavailableError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every handler, so each failure leaves as `code` plus `message`."""
    # Starlette picks by class, so every `BaseDomainException` subclass lands on one handler.
    app.add_exception_handler(BaseDomainException, handle_domain_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    # Only a store that cannot be reached is worth a retry; a constraint violation is a bug, a 500.
    for unreachable_store_error in (OperationalError, InterfaceError, PoolTimeoutError):
        app.add_exception_handler(unreachable_store_error, handle_storage_failure)


async def handle_domain_exception(_request: Request, error: Exception) -> JSONResponse:
    """A refusal answers with the status code its own class carries."""
    refusal = error if isinstance(error, BaseDomainException) else BaseDomainException()
    return JSONResponse(
        status_code=refusal.status_code,
        content={'code': refusal.code, 'message': refusal.message},
    )


async def handle_validation_error(_request: Request, error: Exception) -> JSONResponse:
    """Reshape the framework's own 422 into the body every other failure uses."""
    errors = error.errors() if isinstance(error, RequestValidationError) else []
    fields = sorted(
        {str(location[-1]) for detail in errors if (location := detail.get('loc', ()))},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            'code': 'validation_error',
            'message': 'The request contains an invalid value.',
            'fields': fields,
        },
    )


async def handle_storage_failure(request: Request, error: Exception) -> JSONResponse:
    """A store that is down is a 503, not a 500."""
    logger.error('Storage failure while handling a request', exc_info=error)
    return await handle_domain_exception(request, ServiceUnavailableError())
