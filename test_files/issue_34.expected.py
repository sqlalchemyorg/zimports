import typing
from typing import Any
from typing import TypeVar

if typing.TYPE_CHECKING:
    from .state import InstanceState  # noqa

_T = TypeVar("_T", bound=Any)

