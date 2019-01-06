# coding: utf-8

from sqlalchemy import bindparam
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import select
from sqlalchemy import sql
from sqlalchemy import String
from sqlalchemy.dialects.oracle import base as oracle
from sqlalchemy.sql import column
from sqlalchemy.sql import table
from sqlalchemy.testing import AssertsCompiledSQL
from sqlalchemy.testing import eq_
from sqlalchemy.testing import fixtures
from sqlalchemy.testing.schema import Column
from sqlalchemy.testing.schema import Table
# im a comment
# here, we have a comment


class CompileTest(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = "oracle"

    def i_have_an_import(self):
        import foo

        from bar import bat

    def test_true_false(self):
        self.assert_compile(
            sql.false(), "0"
        )
        self.assert_compile(
            sql.true(),
            "1"
        )

    def test_owner(self):
        meta = MetaData()
        parent = Table('parent', meta, Column('id', Integer,
                       primary_key=True), Column('name', String(50)),
                       schema='ed')
        child = Table('child', meta, Column('id', Integer,
                      primary_key=True), Column('parent_id', Integer,
                      ForeignKey('ed.parent.id')), schema='ed')
        self.assert_compile(parent.join(child),
                            'ed.parent JOIN ed.child ON ed.parent.id = '
                            'ed.child.parent_id')

    def test_subquery(self):
        t = table('sometable', column('col1'), column('col2'))
        s = select([t])
        s = select([s.c.col1, s.c.col2])

        self.assert_compile(s, "SELECT col1, col2 FROM (SELECT "
                               "sometable.col1 AS col1, sometable.col2 "
                               "AS col2 FROM sometable)")

    def test_bindparam_quote(self):
        """test that bound parameters take on quoting for reserved words,
        column names quote flag enabled."""
        # note: this is only in cx_oracle at the moment.  not sure
        # what other hypothetical oracle dialects might need

        self.assert_compile(
            bindparam("option"), ':"option"'
        )
        self.assert_compile(
            bindparam("plain"), ':plain'
        )
        t = Table("s", MetaData(), Column('plain', Integer, quote=True))
        self.assert_compile(
            t.insert().values(plain=5),
            'INSERT INTO s ("plain") VALUES (:"plain")'
        )
        self.assert_compile(
            t.update().values(plain=5), 'UPDATE s SET "plain"=:"plain"'
        )

    def test_cte(self):
        part = table(
            'part',
            column('part'),
            column('sub_part'),
            column('quantity')
        )

        included_parts = select([
            part.c.sub_part, part.c.part, part.c.quantity
        ]).where(part.c.part == "p1").\
            cte(name="included_parts", recursive=True).\
            suffix_with(
                "search depth first by part set ord1",
                "cycle part set y_cycle to 1 default 0", dialect='oracle')

        incl_alias = included_parts.alias("pr1")
        parts_alias = part.alias("p")
        included_parts = included_parts.union_all(
            select([
                parts_alias.c.sub_part,
                parts_alias.c.part, parts_alias.c.quantity
            ]).where(parts_alias.c.part == incl_alias.c.sub_part)
        )

        q = select([
            included_parts.c.sub_part,
            func.sum(included_parts.c.quantity).label('total_quantity')]).\
            group_by(included_parts.c.sub_part)

        self.assert_compile(
            q,
            "WITH included_parts(sub_part, part, quantity) AS "
            "(SELECT part.sub_part AS sub_part, part.part AS part, "
            "part.quantity AS quantity FROM part WHERE part.part = :part_1 "
            "UNION ALL SELECT p.sub_part AS sub_part, p.part AS part, "
            "p.quantity AS quantity FROM part p, included_parts pr1 "
            "WHERE p.part = pr1.sub_part) "
            "search depth first by part set ord1 cycle part set "
            "y_cycle to 1 default 0  "
            "SELECT included_parts.sub_part, sum(included_parts.quantity) "
            "AS total_quantity FROM included_parts "
            "GROUP BY included_parts.sub_part"
        )


class CompileTest2(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = "oracle"

    def test_limit(self):
        t = table('sometable', column('col1'), column('col2'))
        s = select([t])
        c = s.compile(dialect=oracle.OracleDialect())
        assert t.c.col1 in set(c._create_result_map()['col1'][1])
        s = select([t]).limit(10).offset(20)
        self.assert_compile(s,
                            'SELECT col1, col2 FROM (SELECT col1, '
                            'col2, ROWNUM AS ora_rn FROM (SELECT '
                            'sometable.col1 AS col1, sometable.col2 AS '
                            'col2 FROM sometable) WHERE ROWNUM <= '
                            ':param_1 + :param_2) WHERE ora_rn > :param_2',
                            checkparams={'param_1': 10, 'param_2': 20})

        c = s.compile(dialect=oracle.OracleDialect())
        eq_(len(c._result_columns), 2)
        assert t.c.col1 in set(c._create_result_map()['col1'][1])

        s2 = select([s.c.col1, s.c.col2])
        self.assert_compile(s2,
                            'SELECT col1, col2 FROM (SELECT col1, col2 '
                            'FROM (SELECT col1, col2, ROWNUM AS ora_rn '
                            'FROM (SELECT sometable.col1 AS col1, '
                            'sometable.col2 AS col2 FROM sometable) '
                            'WHERE ROWNUM <= :param_1 + :param_2) '
                            'WHERE ora_rn > :param_2)',
                            checkparams={'param_1': 10, 'param_2': 20})

        self.assert_compile(s2,
                            'SELECT col1, col2 FROM (SELECT col1, col2 '
                            'FROM (SELECT col1, col2, ROWNUM AS ora_rn '
                            'FROM (SELECT sometable.col1 AS col1, '
                            'sometable.col2 AS col2 FROM sometable) '
                            'WHERE ROWNUM <= :param_1 + :param_2) '
                            'WHERE ora_rn > :param_2)')
        c = s2.compile(dialect=oracle.OracleDialect())
        eq_(len(c._result_columns), 2)
        assert s.c.col1 in set(c._create_result_map()['col1'][1])

        s = select([t]).limit(10).offset(20).order_by(t.c.col2)
        self.assert_compile(s,
                            'SELECT col1, col2 FROM (SELECT col1, '
                            'col2, ROWNUM AS ora_rn FROM (SELECT '
                            'sometable.col1 AS col1, sometable.col2 AS '
                            'col2 FROM sometable ORDER BY '
                            'sometable.col2) WHERE ROWNUM <= '
                            ':param_1 + :param_2) WHERE ora_rn > :param_2',
                            checkparams={'param_1': 10, 'param_2': 20}
                            )
        c = s.compile(dialect=oracle.OracleDialect())
        eq_(len(c._result_columns), 2)
        assert t.c.col1 in set(c._create_result_map()['col1'][1])

        s = select([t], for_update=True).limit(10).order_by(t.c.col2)
        self.assert_compile(s,
                            'SELECT col1, col2 FROM (SELECT '
                            'sometable.col1 AS col1, sometable.col2 AS '
                            'col2 FROM sometable ORDER BY '
                            'sometable.col2) WHERE ROWNUM <= :param_1 '
                            'FOR UPDATE')

        s = select([t],
                   for_update=True).limit(10).offset(20).order_by(t.c.col2)
        self.assert_compile(s,
                            'SELECT col1, col2 FROM (SELECT col1, '
                            'col2, ROWNUM AS ora_rn FROM (SELECT '
                            'sometable.col1 AS col1, sometable.col2 AS '
                            'col2 FROM sometable ORDER BY '
                            'sometable.col2) WHERE ROWNUM <= '
                            ':param_1 + :param_2) WHERE ora_rn > :param_2 FOR '
                            'UPDATE')

    def test_for_update(self):
        table1 = table('mytable',
                       column('myid'), column('name'), column('description'))

        self.assert_compile(
            table1.select(table1.c.myid == 7).with_for_update(),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE")

        self.assert_compile(
            table1
            .select(table1.c.myid == 7)
            .with_for_update(of=table1.c.myid),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 "
            "FOR UPDATE OF mytable.myid")

        self.assert_compile(
            table1.select(table1.c.myid == 7).with_for_update(nowait=True),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE NOWAIT")

        self.assert_compile(
            table1
            .select(table1.c.myid == 7)
            .with_for_update(nowait=True, of=table1.c.myid),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 "
            "FOR UPDATE OF mytable.myid NOWAIT")

        self.assert_compile(
            table1
            .select(table1.c.myid == 7)
            .with_for_update(nowait=True, of=[table1.c.myid, table1.c.name]),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE OF "
            "mytable.myid, mytable.name NOWAIT")

        self.assert_compile(
            table1.select(table1.c.myid == 7)
            .with_for_update(skip_locked=True,
                             of=[table1.c.myid, table1.c.name]),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE OF "
            "mytable.myid, mytable.name SKIP LOCKED")

        # key_share has no effect
        self.assert_compile(
            table1.select(table1.c.myid == 7).with_for_update(key_share=True),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE")

        # read has no effect
        self.assert_compile(
            table1
            .select(table1.c.myid == 7)
            .with_for_update(read=True, key_share=True),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE")

        ta = table1.alias()
        self.assert_compile(
            ta
            .select(ta.c.myid == 7)
            .with_for_update(of=[ta.c.myid, ta.c.name]),
            "SELECT mytable_1.myid, mytable_1.name, mytable_1.description "
            "FROM mytable mytable_1 "
            "WHERE mytable_1.myid = :myid_1 FOR UPDATE OF "
            "mytable_1.myid, mytable_1.name"
        )

