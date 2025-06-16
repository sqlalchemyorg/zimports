import asyncio
from contextvars import copy_context as _copy_context
import sys
import typing
from typing import Annotated  # type: ignore[foo-bar]
from typing import Any
from typing import Awaitable  # type: ignore[123]
from typing import ByteString  # type: ignore[foo-bar] # noqa F501
from typing import Callable  # type: ignore # noqa F401
from typing import ClassVar  # type: ignore[123] # noqa F123
from typing import Coroutine

import greenlet  # type: ignore # noqa F401


# keep imports around
vars = [
    Any,
    Callable,
    Coroutine,
    _copy_context,
    sys,
    typing,
    asyncio,
    Annotated,
    Awaitable,
    ByteString,
    ClassVar,
]