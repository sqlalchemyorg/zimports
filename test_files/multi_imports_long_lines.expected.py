# schema.py
# Copyright (C) 2005-2017 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Compatibility namespace for sqlalchemy.sql.schema and related.

"""

from .sql.base import SchemaVisitor
from .sql.ddl import (
    _CreateDropBase, _DDLCompiles, _DropView, AddConstraint, CreateColumn,
    CreateIndex, CreateSchema, CreateSequence, CreateTable, DDL, DDLBase,
    DDLElement, DropColumnComment, DropConstraint, DropIndex, DropSchema,
    DropSequence, DropTable, DropTableComment, SetColumnComment,
    SetTableComment, sort_tables, sort_tables_and_constraints)
from .sql.naming import conv
from .sql.schema import (
    _get_table_key, BLANK_SCHEMA, CheckConstraint, Column,
    ColumnCollectionConstraint, ColumnCollectionMixin, ColumnDefault,
    Constraint, DefaultClause, DefaultGenerator, FetchedValue, ForeignKey,
    ForeignKeyConstraint, Index, MetaData, PassiveDefault,
    PrimaryKeyConstraint, SchemaItem, Sequence, Table, ThreadLocalMetaData,
    UniqueConstraint)
