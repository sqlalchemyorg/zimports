from sqlalchemy import ARRAY, BIGINT, BINARY, BLANK_SCHEMA, BLOB, BOOLEAN, BigInteger, Binary, Boolean, CHAR, CLOB, CheckConstraint, Column, ColumnDefault, Constraint, DATE, DATETIME, DDL, DECIMAL, Date, DateTime, DefaultClause, Enum, FLOAT, FetchedValue, Float, ForeignKey, ForeignKeyConstraint, INT, INTEGER, Index, Integer, Interval, JSON, LargeBinary, MetaData, NCHAR, NUMERIC, NVARCHAR, Numeric, PassiveDefault, PickleType, PrimaryKeyConstraint, REAL, SMALLINT, Sequence, SmallInteger, String, TEXT, TIME, TIMESTAMP, Table, Text, ThreadLocalMetaData, Time, TypeDecorator, Unicode, UnicodeText, UniqueConstraint, VARBINARY, VARCHAR, alias, all_, and_, any_, asc, between, bindparam, case, cast, collate, column, create_engine, delete, desc, distinct, engine_from_config, except_, except_all, exists, extract, false, func, funcfilter, insert, inspect, intersect, intersect_all, join, lateral, literal, literal_column, modifier, not_, null, nullsfirst, nullslast, or_, outerjoin, outparam, over, select, subquery, table, tablesample, text, true, tuple_, type_coerce, union, union_all, update, within_group
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import AliasOption, AttributeExtension, Bundle, ColumnProperty, ComparableProperty, CompositeProperty, EXT_CONTINUE, EXT_SKIP, EXT_STOP, Load, Mapper, MapperExtension, PropComparator, Query, RelationshipProperty, Session, SessionExtension, SynonymProperty, aliased, backref, class_mapper, clear_mappers, column_property, comparable_property, compile_mappers, composite, configure_mappers, contains_alias, contains_eager, create_session, defaultload, defer, deferred, dynamic_loader, eagerload, eagerload_all, foreign, immediateload, join, joinedload, joinedload_all, lazyload, lazyload_all, load_only, make_transient, make_transient_to_detached, mapper, noload, object_mapper, object_session, outerjoin, polymorphic_union, public_factory, query_expression, raiseload, reconstructor, relation, relationship, remote, scoped_session, selectin_polymorphic, selectinload, selectinload_all, sessionmaker, subqueryload, subqueryload_all, synonym, undefer, undefer_group, validates, was_deleted, with_expression, with_parent, with_polymorphic
from sqlalchemy.testing import assert_raises_message
from sqlalchemy.testing import fixtures
from sqlalchemy import testing


class CompileTest(fixtures.ORMTest):
    """test various mapper compilation scenarios"""

    def teardown(self):
        clear_mappers()

    def test_with_polymorphic(self):
        metadata = MetaData(testing.db)

        order = Table('orders', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('employee_id', Integer, ForeignKey(
                          'employees.id'), nullable=False),
                      Column('type', Unicode(16)))

        employee = Table('employees', metadata,
                         Column('id', Integer, primary_key=True),
                         Column('name', Unicode(16), unique=True,
                                nullable=False))

        product = Table('products', metadata,
                        Column('id', Integer, primary_key=True))

        orderproduct = Table('orderproducts', metadata,
                             Column('id', Integer, primary_key=True),
                             Column('order_id', Integer, ForeignKey(
                                 "orders.id"), nullable=False),
                             Column('product_id', Integer, ForeignKey(
                                 "products.id"), nullable=False))

        class Order(object):
            pass

        class Employee(object):
            pass

        class Product(object):
            pass

        class OrderProduct(object):
            pass

        order_join = order.select().alias('pjoin')

        order_mapper = mapper(Order, order,
                              with_polymorphic=('*', order_join),
                              polymorphic_on=order_join.c.type,
                              polymorphic_identity='order',
                              properties={
                                  'orderproducts': relationship(
                                      OrderProduct, lazy='select',
                                      backref='order')}
                              )

        mapper(Product, product,
               properties={
                   'orderproducts': relationship(OrderProduct, lazy='select',
                                                 backref='product')}
               )

        mapper(Employee, employee,
               properties={
                   'orders': relationship(Order, lazy='select',
                                          backref='employee')})

        mapper(OrderProduct, orderproduct)

        # this requires that the compilation of order_mapper's "surrogate
        # mapper" occur after the initial setup of MapperProperty objects on
        # the mapper.
        configure_mappers()

    def test_conflicting_backref_one(self):
        """test that conflicting backrefs raises an exception"""

        metadata = MetaData(testing.db)

        order = Table('orders', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('type', Unicode(16)))

        product = Table('products', metadata,
                        Column('id', Integer, primary_key=True))

        orderproduct = Table('orderproducts', metadata,
                             Column('id', Integer, primary_key=True),
                             Column('order_id', Integer,
                                    ForeignKey("orders.id"), nullable=False),
                             Column('product_id', Integer,
                                    ForeignKey("products.id"),
                                    nullable=False))

        class Order(object):
            pass

        class Product(object):
            pass

        class OrderProduct(object):
            pass

        order_join = order.select().alias('pjoin')

        order_mapper = mapper(Order, order,
                              with_polymorphic=('*', order_join),
                              polymorphic_on=order_join.c.type,
                              polymorphic_identity='order',
                              properties={
                                  'orderproducts': relationship(
                                      OrderProduct, lazy='select',
                                      backref='product')}
                              )

        mapper(Product, product,
               properties={
                   'orderproducts': relationship(OrderProduct, lazy='select',
                                                 backref='product')}
               )

        mapper(OrderProduct, orderproduct)

        assert_raises_message(
            sa_exc.ArgumentError,
            "Error creating backref",
            configure_mappers
        )

    def test_misc_one(self):
        metadata = MetaData(testing.db)
        node_table = Table("node", metadata,
                           Column('node_id', Integer, primary_key=True),
                           Column('name_index', Integer, nullable=True))
        node_name_table = Table("node_name", metadata,
                                Column('node_name_id', Integer,
                                       primary_key=True),
                                Column('node_id', Integer,
                                       ForeignKey('node.node_id')),
                                Column('host_id', Integer,
                                       ForeignKey('host.host_id')),
                                Column('name', String(64), nullable=False))
        host_table = Table("host", metadata,
                           Column('host_id', Integer, primary_key=True),
                           Column('hostname', String(64), nullable=False,
                                  unique=True))
        metadata.create_all()
        try:
            node_table.insert().execute(node_id=1, node_index=5)

            class Node(object):
                pass

            class NodeName(object):
                pass

            class Host(object):
                pass

            node_mapper = mapper(Node, node_table)
            host_mapper = mapper(Host, host_table)
            node_name_mapper = mapper(NodeName, node_name_table,
                                      properties={
                                          'node': relationship(
                                              Node, backref=backref('names')),
                                          'host': relationship(Host),
                                      })
            sess = create_session()
            assert sess.query(Node).get(1).names == []
        finally:
            metadata.drop_all()

    def test_conflicting_backref_two(self):
        meta = MetaData()

        a = Table('a', meta, Column('id', Integer, primary_key=True))
        b = Table('b', meta, Column('id', Integer, primary_key=True),
                  Column('a_id', Integer, ForeignKey('a.id')))

        class A(object):
            pass

        class B(object):
            pass

        mapper(A, a, properties={
            'b': relationship(B, backref='a')
        })
        mapper(B, b, properties={
            'a': relationship(A, backref='b')
        })

        assert_raises_message(
            sa_exc.ArgumentError,
            "Error creating backref",
            configure_mappers
        )

    def test_conflicting_backref_subclass(self):
        meta = MetaData()

        a = Table('a', meta, Column('id', Integer, primary_key=True))
        b = Table('b', meta, Column('id', Integer, primary_key=True),
                  Column('a_id', Integer, ForeignKey('a.id')))

        class A(object):
            pass

        class B(object):
            pass

        class C(B):
            pass

        mapper(A, a, properties={
            'b': relationship(B, backref='a'),
            'c': relationship(C, backref='a')
        })
        mapper(B, b)
        mapper(C, None, inherits=B)

        assert_raises_message(
            sa_exc.ArgumentError,
            "Error creating backref",
            configure_mappers
        )
