import sys, os
from . import cat, loop
from . import foo, bar


def go():
    argv = sys.argv
    path = os.getcwd()
    print(argv, path)
    return foo() + bar() + cat() + loop()
