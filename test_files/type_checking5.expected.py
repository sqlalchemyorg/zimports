import os
import sys
import typing

if typing.TYPE_CHECKING:
    print("hi")

    from typing import Generic
    from typing import Type
else:
    print("there")
    from otherpackage import Type


print(sys.path)
print(os.environ)




if TYPE_CHECKING:
    pass
else:
    print("keep this here")