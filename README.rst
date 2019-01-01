========
zimports
========

Reformats Python imports so that they can pass flake8-import-order.  This is
roughly:

* one import per line

* alphabetically sorted

* grouped by builtin / external library / current application

* unused imports removed

Currently we are conforming to the "google" style at:

https://github.com/PyCQA/flake8-import-order/blob/master/tests/test_cases/complete_google.py

because I'm using flake8-import-order using that style, which most closely
matched what I had this program doing at first (which is really mostly like the Openstack
style).


zzzeek why are you writing one of these, there are a dozen pep8 import fixers
=============================================================================

I've just gone through a whole bunch.     I need one that:

* has shell capability, not only a plugin for vim or sublime text (Python Fix Imports, gratis)

* Removes unused imports, not just reformats them (importanize)

* Reformats imports, not just removes unused ones (autoflake)

* Doesn't miss removing an import that isn't used just because it's on a
  multiline import (autoflake)

* Breaks up *all* imports into individual lines, not just if the line is >80 char
  (importanize)

* Is extremely simple because (since pyflakes does most of the hard work) this is
  an extremely simple job (e.g. isn't a dozen source files)
