import typing

import sys
import os

if typing.TYPE_CHECKING:
    print("hi")

    from typing import Type
else:
    print("there")
    from otherpackage import Type


print(sys.path)
print(os.environ)



if typing.TYPE_CHECKING:
    from typing import Generic
else:
    print("keep this here")