import os
import sys

from . import bar, foo
from . import cat, loop


def go():
    argv = sys.argv
    path = os.getcwd()
    print(argv, path)
    return foo() + bar() + cat() + loop()
