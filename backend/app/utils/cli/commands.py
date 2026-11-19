import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any


def async_command[**P, R](
    command: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, R]:
    """`command`, a coroutine function, as a function Typer can call: Typer calls
    commands synchronously, so each call runs it in an event loop of its own."""

    @functools.wraps(command)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        return asyncio.run(command(*args, **kwargs))

    return run
