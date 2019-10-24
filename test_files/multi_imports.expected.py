from . import bar, foo
from . import cat, loop


def go():
    return foo() + bar() + cat() + loop()
