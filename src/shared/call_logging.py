import functools
import inspect
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger('video_helper.calls')


def log_call[**ParametersT, ReturnT](
    function: Callable[ParametersT, Awaitable[ReturnT]],
) -> Callable[ParametersT, Awaitable[ReturnT]]:
    """Log `Class.method(name=value, ...)` before the call runs; a credential hides via repr."""
    signature = inspect.signature(function)

    @functools.wraps(function)
    async def logged_function(*args: ParametersT.args, **kwargs: ParametersT.kwargs) -> ReturnT:
        if logger.isEnabledFor(logging.INFO):
            bound_arguments = signature.bind(*args, **kwargs).arguments
            bound_arguments.pop('self', None)
            logger.info(
                '%s(%s)',
                function.__qualname__,
                ', '.join(f'{name}={value!r}' for name, value in bound_arguments.items()),
            )
        return await function(*args, **kwargs)

    return logged_function
