import asyncio
import sys
import typing
import greenlet  # type: ignore # noqa F401
from typing import Any
from typing import Callable  # type: ignore
from typing import Coroutine

from contextvars import copy_context as _copy_context  # noqa nosort


# keep imports around
a1 = Any
a2 = Callable
a3 = Coroutine
a4 = _copy_context
a5 = sys
a6 = typing
a7 = asyncio
