# engine/base.py
# Copyright (C) 2005-2018 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php
from __future__ import with_statement

"""Defines :class:`.Connection` and :class:`.Engine`.

"""


import sys
from .. import exc, util, log, interfaces
from ..sql import util as sql_util
from ..sql import schema
from .interfaces import Connectable, ExceptionContext
from .util import _distill_params
import contextlib


class Connection(Connectable):
    """Provides high-level functionality for a wrapped DB-API connection.

    Provides execution support for string-based SQL statements as well as
    :class:`.ClauseElement`, :class:`.Compiled` and :class:`.DefaultGenerator`
    objects. Provides a :meth:`begin` method to return :class:`.Transaction`
    objects.

    The Connection object is **not** thread-safe.  While a Connection can be
    shared among threads using properly synchronized access, it is still
    possible that the underlying DBAPI connection may not support shared
    access between threads.  Check the DBAPI documentation for details.

    The Connection object represents a single dbapi connection checked out
    from the connection pool. In this state, the connection pool has no affect
    upon the connection, including its expiration or timeout state. For the
    connection pool to properly manage connections, connections should be
    returned to the connection pool (i.e. ``connection.close()``) whenever the
    connection is not in use.

    .. index::
      single: thread safety; Connection

    """

    schema_for_object = schema._schema_getter(None)
