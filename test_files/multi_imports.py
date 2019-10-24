from . import cat, loop
from . import foo, bar


def go():
    return foo() + bar() + cat() + loop()
