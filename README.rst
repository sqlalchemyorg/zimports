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
  removing all the unused names

* support for TYPE_CHECKING import blocks.

The program currently bolts itself on top of `flake8-import-order
<https://github.com/PyCQA/flake8-import-order/>`_, in order to reuse the import
classification and sorting styles that tool provides. Without options given,
the script will look directly for a ``setup.cfg`` file with a ``[flake8]``
section and will consume flake8-import-order parameters ``"application-import-
names"``, ``"application-package-names"``, and ``"import-order-style"``, to
sort imports exactly as this linter then expects to find them.   All of the
single-line import styles, e.g. google, cryptography, pycharm, should just
work.

Special classifications can be given to imports, as either a "  # noqa" comment
indicating the import should not be removed, and optionally
the comment "  # noqa nosort" which will place the import into a special
"don't sort" category, placing all of the "nosort" imports in the order
they originally appeared, grouped after all the sorted imports.  This can
be used for special situations where a few imports have to be in a certain
order against each other (SQLAlchemy has two lines like this at the moment).

The application also does not affect imports that are inside of conditionals
or defs, or otherwise indented in any way, with the exception of TYPE_CHECKING
imports.  This is also the behavior of
flake8-import-order; only imports in column zero of the source file are
counted, although imports that are on lines below other definitions are
counted, which are moved up to the top section of the source file.

.. note::  This application runs in **Python 3 only**.  It can reformat
   imports for Python 2 code as well but internally it uses library
   and language features only available in Python 3.


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

But what about... isort ??
--------------------------

Since I developed zimports some years ago and now have it on all my projects,
isort has come out and is widely becoming accepted as the de-facto import
sorter, because it's actually super nice and has tons of features.  It popped up
turned on by default in my vscode IDE and it's under pycqa, it's clearly the
winning tool in this space.

So I would *like* to use isort, and I've tried it out. I was able to get it 99%
equivalent to how we sort our imports now, with the exception of a weird
relative import issue that still wouldn't compare against
``flake8-import-order`` (it seemed like lexical sorting wasn't working
correctly).   Maybe we can get that little part working, but that's not the main
issue.

The bigger shortcoming was IIUC it, like "importanize" mentioned previously,
just reformats the imports that are present.   It won't remove unused imports,
nor does it have any ability to expand ``import *`` into individual imports,
since it isn't looking at the rest of the code.    zimports actually hangs on top of
``flake8`` so that we can remove unused imports and it also uses ``flake8``
output along with a module import path in order to expand out "*" imports.
I use this feature *all the time* when I type out test scripts for SQLAlchemy,
I just start with ``from sqlalchemy import *`` and have zimports clean it all up.

Maybe there would be a way to keep zimports for that part, and then use isort
for the actual sorting.  But then I'm still just using zimports, and while isort
definitely does a better job at finding imports to sort (it does them inside
method bodies, inside of cython files, wow), it's not really worth it right now
for me to change everything when I still have to maintain zimports anyway.

TL;DR; yes go use isort, I have no desire to support zimports for other people!
:)  zimports does a few things that I personally like a
lot, especially removing unused imports which is totally essential for my
use cases.

Usage
=====

The script can run without any configuration, options are as follows::

  $ zimports --help
  usage: zimports [-h] [-m APPLICATION_IMPORT_NAMES]
                  [-p APPLICATION_PACKAGE_NAMES] [--style STYLE] [--multi-imports]
                  [-k] [-kt] [--heuristic-unused HEURISTIC_UNUSED] [--statsonly]
                  [-e] [--diff] [--stdout]
                  filename [filename ...]

  positional arguments:
    filename              Python filename(s) or directories

  optional arguments:
    -h, --help            show this help message and exit
    -m APPLICATION_IMPORT_NAMES, --application-import-names APPLICATION_IMPORT_NAMES
                          comma separated list of names that should be
                          considered local to the application. reads from
                          [flake8] application-import-names by default.
    -p APPLICATION_PACKAGE_NAMES, --application-package-names APPLICATION_PACKAGE_NAMES
                          comma separated list of names that should be
                          considered local to the organization. reads from
                          [flake8] application-package-names by default.
    --style STYLE         import order styling, reads from [flake8] import-
                          order-style by default, or defaults to 'google'
    --multi-imports       If set, multiple imports can exist on one line
    -k, --keep-unused     keep unused imports even though detected as unused.
                          Implies keep-unused-type-checking
    -kt, --keep-unused-type-checking
                          keep unused imports even though detected as unused in
                          type checking blocks. zimports does not detect type usage
                          in comments or when used as string
    --heuristic-unused HEURISTIC_UNUSED
                          Remove unused imports only if number of imports is
                          less than <HEURISTIC_UNUSED> percent of the total
                          lines of code. Ignored in type checking blocks
    --statsonly           don't write or display anything except the file stats
    -e, --expand-stars    Expand star imports into the names in the actual
                          module, which can then have unused names removed.
                          Requires modules can be imported
    --diff                don't modify files, just dump out diffs
    --stdout              dump file output to stdout

Configuration is currently broken up between consumption of flake8 parameters
from ``setup.cfg``, and then additional zimports parameters in
``pyproject.toml`` (as of version 0.5.0) - unification of these two files will
be in a future release, possibly when flake8 adds toml support::

    # setup.cfg

    [flake8]
    enable-extensions = G
    ignore =
        A003,
        E203,E305,E711,E712,E721,E722,E741,
        F841,
        N801,N802,N806,
        W503,W504
    import-order-style = google
    application-import-names = sqlalchemy,test

    # pyproject.toml, integrated with black

    [tool.black]
    line-length = 79
    target-version = ['py39']


    [tool.zimports]
    black-line-length = 79
    keep-unused-type-checking = true

    # other options:
    # multi-imports = true
    # keep-unused = true

Then, a typical run on a mostly clean source tree looks like::

  $ zimports lib/
  [Unchanged]     lib/sqlalchemy/inspection.py (in 0.0058 sec)
  [Unchanged]     lib/sqlalchemy/log.py (in 0.0221 sec)

  ...

  [Unchanged]     lib/sqlalchemy/orm/attributes.py (in 0.2152 sec)
  [Unchanged]     lib/sqlalchemy/orm/base.py (in 0.0363 sec)
  [Writing]       lib/sqlalchemy/orm/relationships.py ([2% of lines are imports] [source +0L/-2L] [3 imports removed in 0.3287 sec])
  [Unchanged]     lib/sqlalchemy/orm/strategies.py (in 0.2237 sec)

The program has two general modes of usage.  One is that of day-to-day usage
for an application that already has clean imports.   Running zimports on the
source files of such an application should produce no changes, except for
whatever source files were recently edited, and may have some changes to
imports that need to be placed into the correct order. This usage model is
similar to that of `Black <https://github.com/ambv/black>`_, where you can run
"zimports ." and it will find whatever files need adjusting and leave the rest
alone.

The other mode of usage is that of the up-front cleaning up of an application
that has  un- organized imports.   In this mode of usage, the goal is to get
the source files to be cleaned up so that ``zimports`` can be run straight
without any modifications to the file needed, including that all necessary
imports are either used locally or marked as not to be removed.

Problems that can occur during this phase are that some imports are unused and
should be removed, while other imports that are apparently unused are still in
fact imported by other parts of the program.   Another issue is that changing
the ordering of imports in complex cases may cause the application to no longer
run due to the creation of unresolvable import cycles.   Finally,  some
programs have use of ``import *``, pulling in a large list of names for  which
an unknown portion of them are needed by the application.  The options
``--keep-unused``, ``--heuristic-unused`` and ``--expand-stars`` are
provided to assist in working through these issues until the  code can be
fully reformatted such that running ``zimports`` no longer produces changes.

The issue of apparently unused imports that are externally imported  can be
prominent in some applications.  In order to allow imports that aren't locally
used to remain in the source file, symbols that are part of
``__all__`` will not be removed, as will imports that are followed by a ``  #
noqa`` comment.  Either of these techniques should be applied to imports that
are used from other modules but not otherwise referenced within the immediate
source file.   For the less common case that a few imports really need a very
specific import order for things to work, those imports can be followed by a ``
# noqa nosort`` comment that will add these lines to a special group at the end
of all imports, where they will not be removed and their order relative to each
other will be maintained.

The program does currently require that you pass it at least one file or
directory name as an argument.   It also does not have the file caching feature
that Black has, which can allow it to only look at files that have changed
since the last run.  The plan is to have it check that it's inside a git
repository where it will run through files to be committed if no filenames  are
given.

Usage as a ``git`` hook
=======================

``zimports`` can be used with the pre-commit_ git hooks framework.  To add
the plugin, add the following to your ``.pre-commit-config.yaml``.  Note
the ``rev:`` attribute refers to a git tag or revision number of
zimports to be used, such as ``"master"`` or ``"0.1.3"``:

.. code-block:: yaml

    repos:
    -   repo: https://github.com/sqlalchemyorg/zimports/
        rev: v0.4.5
        hooks:
        -   id: zimports


.. _pre-commit: https://pre-commit.com/
