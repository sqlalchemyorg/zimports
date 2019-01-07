========
zimports
========

Reformats Python imports so that they can pass flake8-import-order.  This is
roughly:

* one import per line

* alphabetically sorted, with stylistic options for how dots, case sensitivity,
  and dotted names are sorted

* grouped by builtin / external library / current application (also
  stylistically controllable)

* unused imports removed, using pyflakes to match "unused import" warnings
  to actual lines of code

* duplicate imports removed (note this does not yet include duplicate symbol
  names against different imports)

* no star imports (e.g. ``from <foo> import *``); these are rewritten as
  explicit names, by importing all the names from each target module and then
  removing all the unused names.

The program now bolts itself on top of flake8-import-order, at
https://github.com/PyCQA/flake8-import-order/, in order to reuse the
import classification and sorting styles present there.    Without options
given, the script will look directly for a setup.cfg file with a ``[flake8]``
section and will consume flake8-import-order parameters
``"application-import-names"``,  ``"application-package-names"``,
and ``"import-order-style"``, to sort imports exactly as this linter
then expects to find them.   All of the single-line import styles, e.g.
google, cryptography, pycharm, should just work.

Special classifications can be given to imports, as either a "  # noqa" comment
indicating the import should not be removed, and optionally
the comment "  # noqa nosort" which will place the import into a special
"don't sort" category, placing all of the "nosort" imports in the order
they originally appeared, grouped after all the sorted imports.  This can
be used for special situations where a few imports have to be in a certain
order against each other (SQLAlchemy has two lines like this at the moment).

The application also does not affect imports that are inside of conditionals
or defs, or otherwise indented in any way.  This is also the behavior of
flake8-import-order; only imports in column zero of the source file are
counted, although imports that are on lines below other definitions are
counted, which are moved up to the top section of the source file.

zzzeek why are you writing one of these, there are a dozen pep8 import fixers
=============================================================================

I've just gone through a whole bunch.     I need one that:

* works directly with flake8-import-order so we are guaranteed to have a match

* has shell capability, not only a plugin for vim or sublime text (Python Fix
  Imports, gratis)

* Removes unused imports, not just reformats them (importanize)

* Reformats imports, not just removes unused ones (autoflake)

* Doesn't miss removing an import that isn't used just because it's on a
  multiline import (autoflake)

* Breaks up *all* imports into individual lines, not just if the line is >80 char
  (importanize)

* Is still pretty simple (we're a bit beyond our original "extremely" simple
  baseline, because all problems are ultimately not that simple) because (since
  pyflakes and now flake8-import-order do most of the hard work) this is an
  extremely simple job, there's (still) no  need for a giant application here.
