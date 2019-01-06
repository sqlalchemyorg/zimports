import sqlalchemy.orm
import json
import os

from ..bar import bars
from sqlalchemy import Table
from sqlalchemy.dialects.oracle import cx_oracle
from sqlalchemy import Column
from sqlalchemy.ext import declarative
from sqlalchemy.sql import select, cast, select, label
from sqlalchemy import Sequence, Table, ForeignKey


from .bat import dupe1
from .bat import dupe1  # noqa
from .bat import dupe1

from .foo import assertions
from ..foo import assertions
from ..bar import bars
import os


from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table


t = Table(Column(cx_oracle.FOO, ForeignKey()))

b = declarative_base(declarative.bar())
os.path.join(json.dumps({"foo": bars.bar}))

stmt = select([cast(t.c.foo), 'bar'])
assertions.assert_(sqlalchemy.orm.bat())