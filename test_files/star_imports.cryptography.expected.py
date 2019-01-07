from test.orm import _fixtures

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import exc as sa_exc
from sqlalchemy import literal_column
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased
from sqlalchemy.orm import backref
from sqlalchemy.orm import configure_mappers
from sqlalchemy.orm import create_session
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relationship
from sqlalchemy.orm import synonym
from sqlalchemy.testing import AssertsCompiledSQL
from sqlalchemy.testing import assert_raises
from sqlalchemy.testing import assert_raises_message
from sqlalchemy.testing import eq_
from sqlalchemy.testing import fixtures
from sqlalchemy.testing.schema import Column


class QueryTest(_fixtures.FixtureTest):
    run_setup_mappers = 'once'
    run_inserts = 'once'
    run_deletes = None

    @classmethod
    def setup_mappers(cls):
        Node, composite_pk_table, users, Keyword, items, Dingaling, \
            order_items, item_keywords, Item, User, dingalings, \
            Address, keywords, CompositePk, nodes, Order, orders, \
            addresses = cls.classes.Node, \
            cls.tables.composite_pk_table, cls.tables.users, \
            cls.classes.Keyword, cls.tables.items, \
            cls.classes.Dingaling, cls.tables.order_items, \
            cls.tables.item_keywords, cls.classes.Item, \
            cls.classes.User, cls.tables.dingalings, \
            cls.classes.Address, cls.tables.keywords, \
            cls.classes.CompositePk, cls.tables.nodes, \
            cls.classes.Order, cls.tables.orders, cls.tables.addresses

        mapper(User, users, properties={
            'addresses': relationship(Address, backref='user',
                                      order_by=addresses.c.id),
            # o2m, m2o
            'orders': relationship(Order, backref='user', order_by=orders.c.id)
        })
        mapper(Address, addresses, properties={
            # o2o
            'dingaling': relationship(Dingaling, uselist=False,
                                      backref="address")
        })
        mapper(Dingaling, dingalings)
        mapper(Order, orders, properties={
            # m2m
            'items': relationship(Item, secondary=order_items,
                                  order_by=items.c.id),
            'address': relationship(Address),  # m2o
        })
        mapper(Item, items, properties={
            'keywords': relationship(Keyword, secondary=item_keywords)  # m2m
        })
        mapper(Keyword, keywords)

        mapper(Node, nodes, properties={
            'children': relationship(Node,
                                     backref=backref(
                                         'parent', remote_side=[nodes.c.id]))
        })

        mapper(CompositePk, composite_pk_table)

        configure_mappers()


class InheritedJoinTest(fixtures.MappedTest, AssertsCompiledSQL):
    run_setup_mappers = 'once'

    @classmethod
    def define_tables(cls, metadata):
        Table('companies', metadata,
              Column('company_id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('name', String(50)))

        Table('people', metadata,
              Column('person_id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('company_id', Integer,
                     ForeignKey('companies.company_id')),
              Column('name', String(50)),
              Column('type', String(30)))

        Table('engineers', metadata,
              Column('person_id', Integer, ForeignKey(
                  'people.person_id'), primary_key=True),
              Column('status', String(30)),
              Column('engineer_name', String(50)),
              Column('primary_language', String(50)))

        Table('machines', metadata,
              Column('machine_id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('name', String(50)),
              Column('engineer_id', Integer,
                     ForeignKey('engineers.person_id')))

        Table('managers', metadata,
              Column('person_id', Integer, ForeignKey(
                  'people.person_id'), primary_key=True),
              Column('status', String(30)),
              Column('manager_name', String(50)))

        Table('boss', metadata,
              Column('boss_id', Integer, ForeignKey(
                  'managers.person_id'), primary_key=True),
              Column('golf_swing', String(30)),
              )

        Table('paperwork', metadata,
              Column('paperwork_id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('description', String(50)),
              Column('person_id', Integer, ForeignKey('people.person_id')))

    @classmethod
    def setup_classes(cls):
        paperwork, people, companies, boss, managers, machines, engineers = (
            cls.tables.paperwork,
            cls.tables.people,
            cls.tables.companies,
            cls.tables.boss,
            cls.tables.managers,
            cls.tables.machines,
            cls.tables.engineers)

        class Company(cls.Comparable):
            pass

        class Person(cls.Comparable):
            pass

        class Engineer(Person):
            pass

        class Manager(Person):
            pass

        class Boss(Manager):
            pass

        class Machine(cls.Comparable):
            pass

        class Paperwork(cls.Comparable):
            pass

        mapper(Company, companies, properties={
            'employees': relationship(Person, order_by=people.c.person_id)
        })

        mapper(Machine, machines)

        mapper(Person, people,
               polymorphic_on=people.c.type,
               polymorphic_identity='person',
               properties={
                   'paperwork': relationship(Paperwork,
                                             order_by=paperwork.c.paperwork_id)
               })
        mapper(Engineer, engineers, inherits=Person,
               polymorphic_identity='engineer',
               properties={'machines': relationship(
                   Machine, order_by=machines.c.machine_id)})
        mapper(Manager, managers,
               inherits=Person, polymorphic_identity='manager')
        mapper(Boss, boss, inherits=Manager, polymorphic_identity='boss')
        mapper(Paperwork, paperwork)

    def test_single_prop(self):
        Company = self.classes.Company

        sess = create_session()

        self.assert_compile(
            sess.query(Company).join(Company.employees),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies JOIN people "
            "ON companies.company_id = people.company_id",
            use_default_dialect=True)

    def test_force_via_select_from(self):
        Company, Engineer = self.classes.Company, self.classes.Engineer

        sess = create_session()

        self.assert_compile(
            sess.query(Company)
            .filter(Company.company_id == Engineer.company_id)
            .filter(Engineer.primary_language == 'java'),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies, people, engineers "
            "WHERE companies.company_id = people.company_id "
            "AND engineers.primary_language "
            "= :primary_language_1", use_default_dialect=True)

        self.assert_compile(
            sess.query(Company).select_from(Company, Engineer)
            .filter(Company.company_id == Engineer.company_id)
            .filter(Engineer.primary_language == 'java'),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies, people JOIN engineers "
            "ON people.person_id = engineers.person_id "
            "WHERE companies.company_id = people.company_id "
            "AND engineers.primary_language ="
            " :primary_language_1", use_default_dialect=True)

    def test_single_prop_of_type(self):
        Company, Engineer = self.classes.Company, self.classes.Engineer

        sess = create_session()

        self.assert_compile(
            sess.query(Company).join(Company.employees.of_type(Engineer)),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies JOIN "
            "(people JOIN engineers "
            "ON people.person_id = engineers.person_id) "
            "ON companies.company_id = people.company_id",
            use_default_dialect=True)

    def test_prop_with_polymorphic_1(self):
        Person, Manager, Paperwork = (self.classes.Person,
                                      self.classes.Manager,
                                      self.classes.Paperwork)

        sess = create_session()

        self.assert_compile(
            sess.query(Person).with_polymorphic(Manager).
            order_by(Person.person_id).join('paperwork')
            .filter(Paperwork.description.like('%review%')),
            "SELECT people.person_id AS people_person_id, people.company_id AS"
            " people_company_id, "
            "people.name AS people_name, people.type AS people_type, "
            "managers.person_id AS managers_person_id, "
            "managers.status AS managers_status, managers.manager_name AS "
            "managers_manager_name FROM people "
            "LEFT OUTER JOIN managers "
            "ON people.person_id = managers.person_id "
            "JOIN paperwork "
            "ON people.person_id = paperwork.person_id "
            "WHERE paperwork.description LIKE :description_1 "
            "ORDER BY people.person_id", use_default_dialect=True)

    def test_prop_with_polymorphic_2(self):
        Person, Manager, Paperwork = (self.classes.Person,
                                      self.classes.Manager,
                                      self.classes.Paperwork)

        sess = create_session()

        self.assert_compile(
            sess.query(Person).with_polymorphic(Manager).
            order_by(Person.person_id).join('paperwork', aliased=True)
            .filter(Paperwork.description.like('%review%')),
            "SELECT people.person_id AS people_person_id, "
            "people.company_id AS people_company_id, "
            "people.name AS people_name, people.type AS people_type, "
            "managers.person_id AS managers_person_id, "
            "managers.status AS managers_status, "
            "managers.manager_name AS managers_manager_name "
            "FROM people LEFT OUTER JOIN managers "
            "ON people.person_id = managers.person_id "
            "JOIN paperwork AS paperwork_1 "
            "ON people.person_id = paperwork_1.person_id "
            "WHERE paperwork_1.description "
            "LIKE :description_1 ORDER BY people.person_id",
            use_default_dialect=True)

    def test_explicit_polymorphic_join_one(self):
        Company, Engineer = self.classes.Company, self.classes.Engineer

        sess = create_session()

        self.assert_compile(
            sess.query(Company).join(Engineer)
            .filter(Engineer.engineer_name == 'vlad'),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies JOIN (people JOIN engineers "
            "ON people.person_id = engineers.person_id) "
            "ON "
            "companies.company_id = people.company_id "
            "WHERE engineers.engineer_name = :engineer_name_1",
            use_default_dialect=True)

    def test_explicit_polymorphic_join_two(self):
        Company, Engineer = self.classes.Company, self.classes.Engineer

        sess = create_session()
        self.assert_compile(
            sess.query(Company)
            .join(Engineer, Company.company_id == Engineer.company_id)
            .filter(Engineer.engineer_name == 'vlad'),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies JOIN "
            "(people JOIN engineers "
            "ON people.person_id = engineers.person_id) "
            "ON "
            "companies.company_id = people.company_id "
            "WHERE engineers.engineer_name = :engineer_name_1",
            use_default_dialect=True)

    def test_multiple_adaption(self):
        """test that multiple filter() adapters get chained together "
        and work correctly within a multiple-entry join()."""

        people, Company, Machine, engineers, machines, Engineer = (
            self.tables.people,
            self.classes.Company,
            self.classes.Machine,
            self.tables.engineers,
            self.tables.machines,
            self.classes.Engineer)

        sess = create_session()

        self.assert_compile(
            sess.query(Company)
            .join(people.join(engineers), Company.employees)
            .filter(Engineer.name == 'dilbert'),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies JOIN (people "
            "JOIN engineers ON people.person_id = "
            "engineers.person_id) ON companies.company_id = "
            "people.company_id WHERE people.name = :name_1",
            use_default_dialect=True
        )

        mach_alias = machines.select()
        self.assert_compile(
            sess.query(Company).join(people.join(engineers), Company.employees)
            .join(mach_alias, Engineer.machines, from_joinpoint=True).
            filter(Engineer.name == 'dilbert').filter(Machine.name == 'foo'),
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name "
            "FROM companies JOIN (people "
            "JOIN engineers ON people.person_id = "
            "engineers.person_id) ON companies.company_id = "
            "people.company_id JOIN "
            "(SELECT machines.machine_id AS machine_id, "
            "machines.name AS name, "
            "machines.engineer_id AS engineer_id "
            "FROM machines) AS anon_1 "
            "ON engineers.person_id = anon_1.engineer_id "
            "WHERE people.name = :name_1 AND anon_1.name = :name_2",
            use_default_dialect=True
        )

    def test_auto_aliasing_multi_link(self):
        # test [ticket:2903]
        sess = create_session()

        Company, Engineer, Manager, Boss = self.classes.Company, \
            self.classes.Engineer, \
            self.classes.Manager, self.classes.Boss
        q = sess.query(Company).\
            join(Company.employees.of_type(Engineer)).\
            join(Company.employees.of_type(Manager)).\
            join(Company.employees.of_type(Boss))

        self.assert_compile(
            q,
            "SELECT companies.company_id AS companies_company_id, "
            "companies.name AS companies_name FROM companies "
            "JOIN (people JOIN engineers "
            "ON people.person_id = engineers.person_id) "
            "ON companies.company_id = people.company_id "
            "JOIN (people AS people_1 JOIN managers AS managers_1 "
            "ON people_1.person_id = managers_1.person_id) "
            "ON companies.company_id = people_1.company_id "
            "JOIN (people AS people_2 JOIN managers AS managers_2 "
            "ON people_2.person_id = managers_2.person_id JOIN boss AS boss_1 "
            "ON managers_2.person_id = boss_1.boss_id) "
            "ON companies.company_id = people_2.company_id",
            use_default_dialect=True)


class JoinOnSynonymTest(_fixtures.FixtureTest, AssertsCompiledSQL):
    __dialect__ = 'default'

    @classmethod
    def setup_mappers(cls):
        User = cls.classes.User
        Address = cls.classes.Address
        users, addresses = (cls.tables.users, cls.tables.addresses)
        mapper(User, users, properties={
            'addresses': relationship(Address),
            'ad_syn': synonym("addresses")
        })
        mapper(Address, addresses)

    def test_join_on_synonym(self):
        User = self.classes.User
        self.assert_compile(
            Session().query(User).join(User.ad_syn),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN addresses ON users.id = addresses.user_id"
        )


class JoinTest(QueryTest, AssertsCompiledSQL):
    __dialect__ = 'default'

    def test_single_name(self):
        User = self.classes.User

        sess = create_session()

        self.assert_compile(
            sess.query(User).join("orders"),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders ON users.id = orders.user_id"
        )

        assert_raises(
            sa_exc.InvalidRequestError,
            sess.query(User).join, "user",
        )

        self.assert_compile(
            sess.query(User).join("orders", "items"),
            "SELECT users.id AS users_id, users.name AS users_name FROM users "
            "JOIN orders ON users.id = orders.user_id "
            "JOIN order_items AS order_items_1 "
            "ON orders.id = order_items_1.order_id JOIN items "
            "ON items.id = order_items_1.item_id"
        )

        # test overlapping paths.   User->orders is used by both joins, but
        # rendered once.
        self.assert_compile(
            sess.query(User).join("orders", "items").join(
                "orders", "address"),
            "SELECT users.id AS users_id, users.name AS users_name FROM users "
            "JOIN orders "
            "ON users.id = orders.user_id "
            "JOIN order_items AS order_items_1 "
            "ON orders.id = order_items_1.order_id "
            "JOIN items ON items.id = order_items_1.item_id JOIN addresses "
            "ON addresses.id = orders.address_id")

    def test_invalid_kwarg_join(self):
        User = self.classes.User
        sess = create_session()
        assert_raises_message(
            TypeError,
            "unknown arguments: bar, foob",
            sess.query(User).join, "address", foob="bar", bar="bat"
        )
        assert_raises_message(
            TypeError,
            "unknown arguments: bar, foob",
            sess.query(User).outerjoin, "address", foob="bar", bar="bat"
        )

    def test_left_w_no_entity(self):
        User = self.classes.User
        Address = self.classes.Address

        sess = create_session()

        self.assert_compile(
            sess.query(User, literal_column('x'), ).join(Address),
            "SELECT users.id AS users_id, users.name AS users_name, x "
            "FROM users JOIN addresses ON users.id = addresses.user_id"
        )

        self.assert_compile(
            sess.query(literal_column('x'), User).join(Address),
            "SELECT x, users.id AS users_id, users.name AS users_name "
            "FROM users JOIN addresses ON users.id = addresses.user_id"
        )

    def test_left_is_none_and_query_has_no_entities(self):
        User = self.classes.User
        Address = self.classes.Address

        sess = create_session()

        assert_raises_message(
            sa_exc.InvalidRequestError,
            r"No entities to join from; please use select_from\(\) to "
            r"establish the left entity/selectable of this join",
            sess.query().join, Address
        )

    def test_isouter_flag(self):
        User = self.classes.User

        self.assert_compile(
            create_session().query(User).join('orders', isouter=True),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users LEFT OUTER JOIN orders ON users.id = orders.user_id"
        )

    def test_full_flag(self):
        User = self.classes.User

        self.assert_compile(
            create_session().query(User).outerjoin('orders', full=True),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users FULL OUTER JOIN orders ON users.id = orders.user_id"
        )

    def test_multi_tuple_form(self):
        """test the 'tuple' form of join, now superseded
        by the two-element join() form.

        Not deprecating this style as of yet.

        """

        Item, Order, User = (self.classes.Item,
                             self.classes.Order,
                             self.classes.User)

        sess = create_session()

        # assert_raises(
        #    sa.exc.SADeprecationWarning,
        #    sess.query(User).join, (Order, User.id==Order.user_id)
        # )

        self.assert_compile(
            sess.query(User).join((Order, User.id == Order.user_id)),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders ON users.id = orders.user_id",
        )

        self.assert_compile(
            sess.query(User).join(
                (Order, User.id == Order.user_id),
                (Item, Order.items)),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders ON users.id = orders.user_id "
            "JOIN order_items AS order_items_1 ON orders.id = "
            "order_items_1.order_id JOIN items ON items.id = "
            "order_items_1.item_id",
        )

        # the old "backwards" form
        self.assert_compile(
            sess.query(User).join(("orders", Order)),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders ON users.id = orders.user_id",
        )

    def test_single_prop_1(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        self.assert_compile(
            sess.query(User).join(User.orders),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders ON users.id = orders.user_id"
        )

    def test_single_prop_2(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        self.assert_compile(
            sess.query(User).join(Order.user),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM orders JOIN users ON users.id = orders.user_id"
        )

    def test_single_prop_3(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        oalias1 = aliased(Order)

        self.assert_compile(
            sess.query(User).join(oalias1.user),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM orders AS orders_1 JOIN users ON users.id = orders_1.user_id"
        )

    def test_single_prop_4(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        oalias1 = aliased(Order)
        oalias2 = aliased(Order)
        # another nonsensical query.  (from [ticket:1537]).
        # in this case, the contract of "left to right" is honored
        self.assert_compile(
            sess.query(User).join(oalias1.user).join(oalias2.user),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM orders AS orders_1 JOIN users "
            "ON users.id = orders_1.user_id, "
            "orders AS orders_2 JOIN users ON users.id = orders_2.user_id")

    def test_single_prop_5(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        self.assert_compile(
            sess.query(User).join(User.orders, Order.items),
            "SELECT users.id AS users_id, users.name AS users_name FROM users "
            "JOIN orders ON users.id = orders.user_id "
            "JOIN order_items AS order_items_1 "
            "ON orders.id = order_items_1.order_id JOIN items "
            "ON items.id = order_items_1.item_id"
        )

    def test_single_prop_6(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        ualias = aliased(User)
        self.assert_compile(
            sess.query(ualias).join(ualias.orders),
            "SELECT users_1.id AS users_1_id, users_1.name AS users_1_name "
            "FROM users AS users_1 JOIN orders ON users_1.id = orders.user_id"
        )

    def test_single_prop_7(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        # this query is somewhat nonsensical.  the old system didn't render a
        # correct query for this. In this case its the most faithful to what
        # was asked - there's no linkage between User.orders and "oalias",
        # so two FROM elements are generated.
        oalias = aliased(Order)
        self.assert_compile(
            sess.query(User).join(User.orders, oalias.items),
            "SELECT users.id AS users_id, users.name AS users_name FROM users "
            "JOIN orders ON users.id = orders.user_id, "
            "orders AS orders_1 JOIN order_items AS order_items_1 "
            "ON orders_1.id = order_items_1.order_id "
            "JOIN items ON items.id = order_items_1.item_id")

    def test_single_prop_8(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        # same as before using an aliased() for User as well
        ualias = aliased(User)
        oalias = aliased(Order)
        self.assert_compile(
            sess.query(ualias).join(ualias.orders, oalias.items),
            "SELECT users_1.id AS users_1_id, users_1.name AS users_1_name "
            "FROM users AS users_1 "
            "JOIN orders ON users_1.id = orders.user_id, "
            "orders AS orders_1 JOIN order_items AS order_items_1 "
            "ON orders_1.id = order_items_1.order_id "
            "JOIN items ON items.id = order_items_1.item_id")

    def test_single_prop_9(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        self.assert_compile(
            sess.query(User).filter(User.name == 'ed').from_self().
            join(User.orders),
            "SELECT anon_1.users_id AS anon_1_users_id, "
            "anon_1.users_name AS anon_1_users_name "
            "FROM (SELECT users.id AS users_id, users.name AS users_name "
            "FROM users "
            "WHERE users.name = :name_1) AS anon_1 JOIN orders "
            "ON anon_1.users_id = orders.user_id"
        )

    def test_single_prop_10(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        self.assert_compile(
            sess.query(User).join(User.addresses, aliased=True).
            filter(Address.email_address == 'foo'),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN addresses AS addresses_1 "
            "ON users.id = addresses_1.user_id "
            "WHERE addresses_1.email_address = :email_address_1"
        )

    def test_single_prop_11(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        self.assert_compile(
            sess.query(User).join(User.orders, Order.items, aliased=True).
            filter(Item.id == 10),
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders AS orders_1 "
            "ON users.id = orders_1.user_id "
            "JOIN order_items AS order_items_1 "
            "ON orders_1.id = order_items_1.order_id "
            "JOIN items AS items_1 ON items_1.id = order_items_1.item_id "
            "WHERE items_1.id = :id_1")

    def test_single_prop_12(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        oalias1 = aliased(Order)
        # test #1 for [ticket:1706]
        ualias = aliased(User)
        self.assert_compile(
            sess.query(ualias).
            join(oalias1, ualias.orders).
            join(Address, ualias.addresses),
            "SELECT users_1.id AS users_1_id, users_1.name AS "
            "users_1_name FROM users AS users_1 JOIN orders AS orders_1 "
            "ON users_1.id = orders_1.user_id JOIN addresses ON users_1.id "
            "= addresses.user_id"
        )

    def test_single_prop_13(self):
        Item, Order, User, Address = (self.classes.Item,
                                      self.classes.Order,
                                      self.classes.User,
                                      self.classes.Address)

        sess = create_session()
        # test #2 for [ticket:1706]
        ualias = aliased(User)
        ualias2 = aliased(User)
        self.assert_compile(
            sess.query(ualias).
            join(Address, ualias.addresses).
            join(ualias2, Address.user).
            join(Order, ualias.orders),
            "SELECT users_1.id AS users_1_id, users_1.name AS users_1_name "
            "FROM users "
            "AS users_1 JOIN addresses ON users_1.id = addresses.user_id "
            "JOIN users AS users_2 "
            "ON users_2.id = addresses.user_id JOIN orders "
            "ON users_1.id = orders.user_id"
        )

    def test_overlapping_paths(self):
        User = self.classes.User

        for aliased in (True, False):
            # load a user who has an order that contains item id 3 and address
            # id 1 (order 3, owned by jack)
            result = create_session().query(User) \
                .join('orders', 'items', aliased=aliased) \
                .filter_by(id=3) \
                .join('orders', 'address', aliased=aliased) \
                .filter_by(id=1).all()
            assert [User(id=7, name='jack')] == result

    def test_overlapping_paths_multilevel(self):
        User = self.classes.User

        s = Session()
        q = s.query(User).\
            join('orders').\
            join('addresses').\
            join('orders', 'items').\
            join('addresses', 'dingaling')
        self.assert_compile(
            q,
            "SELECT users.id AS users_id, users.name AS users_name "
            "FROM users JOIN orders ON users.id = orders.user_id "
            "JOIN addresses ON users.id = addresses.user_id "
            "JOIN order_items AS order_items_1 ON orders.id = "
            "order_items_1.order_id "
            "JOIN items ON items.id = order_items_1.item_id "
            "JOIN dingalings ON addresses.id = dingalings.address_id"

        )

    def test_overlapping_paths_outerjoin(self):
        User = self.classes.User

        result = create_session().query(User).outerjoin('orders', 'items') \
            .filter_by(id=3).outerjoin('orders', 'address') \
            .filter_by(id=1).all()
        assert [User(id=7, name='jack')] == result

    def test_raises_on_dupe_target_rel(self):
        User = self.classes.User

        assert_raises_message(
            sa.exc.SAWarning,
            "Pathed join target Order.items has already been joined to; "
            "skipping",
            lambda: create_session().query(User).outerjoin('orders', 'items').
            outerjoin('orders', 'items')
        )

    def test_from_joinpoint(self):
        Item, User, Order = (self.classes.Item,
                             self.classes.User,
                             self.classes.Order)

        sess = create_session()

        for oalias, ialias in [
                (True, True),
                (False, False),
                (True, False),
                (False, True)]:
            eq_(
                sess.query(User).join('orders', aliased=oalias)
                .join('items', from_joinpoint=True, aliased=ialias)
                .filter(Item.description == 'item 4').all(),
                [User(name='jack')]
            )

            # use middle criterion
            eq_(
                sess.query(User).join('orders', aliased=oalias)
                .filter(Order.user_id == 9)
                .join('items', from_joinpoint=True, aliased=ialias)
                .filter(Item.description == 'item 4').all(),
                []
            )

        orderalias = aliased(Order)
        itemalias = aliased(Item)
        eq_(
            sess.query(User).join(orderalias, 'orders')
            .join(itemalias, 'items', from_joinpoint=True)
            .filter(itemalias.description == 'item 4').all(),
            [User(name='jack')]
        )
        eq_(
            sess.query(User).join(orderalias, 'orders')
            .join(itemalias, 'items', from_joinpoint=True)
            .filter(orderalias.user_id == 9)
            .filter(itemalias.description == 'item 4').all(),
            []
        )

