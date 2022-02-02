import typing
from typing import TypeVar
from typing import Any

if typing.TYPE_CHECKING:
    from .state import InstanceState  # noqa

_T = TypeVar("_T", bound=Any)

