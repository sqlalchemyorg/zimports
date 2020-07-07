import json
import os

from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Table
from sqlalchemy.dialects.oracle import cx_oracle
from sqlalchemy.ext import declarative
from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy.orm
from sqlalchemy.sql import cast
from sqlalchemy.sql import select
from .bat import dupe1  # noqa
from .foo import assertions
from ..bar import bars
from ..foo import assertions


t = Table(Column(cx_oracle.FOO, ForeignKey()))

b = declarative_base(declarative.bar())
os.path.join(json.dumps({"foo": bars.bar}))

stmt = select([cast(t.c.foo), 'bar'])
assertions.assert_(sqlalchemy.orm.bat())