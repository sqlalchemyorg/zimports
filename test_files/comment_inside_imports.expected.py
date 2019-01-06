# engine/base.py
# Copyright (C) 2005-2018 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php
from __future__ import with_statement

from .interfaces import Connectable
from ..sql import schema

"""Defines :class:`.Connection` and :class:`.Engine`.

"""


class Connection(Connectable):
    """Provides high-level functionality for a wrapped DB-API connection.

    """

    schema_for_object = schema._schema_getter(None)
