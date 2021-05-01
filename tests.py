import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import zimports


class ImportsTest(unittest.TestCase):
    @contextlib.contextmanager
    def _capture_stdout(self):
        buf = io.StringIO()
        with mock.patch("zimports.zimports.sys", mock.Mock(stdout=buf)):
            yield buf

    @contextlib.contextmanager
    def _simulate_importlib(self):
        def import_module(name):
            if name == "sqlalchemy":
                return self.mock_sqlalchemy
            elif name == "sqlalchemy.orm":
                return self.mock_sqlalchemy_orm
            else:
                raise ImportError(name)

        with mock.patch(
            "zimports.zimports.importlib.import_module", import_module
        ):
            yield

    @contextlib.contextmanager
    def _mock_config(self, config_text):
        from zimports.cli import _load_config

        with tempfile.NamedTemporaryFile("w+", delete=False) as file:
            file.write(config_text)

        def load_config(name=None):
            return _load_config(file.name)

        with mock.patch("zimports.cli._load_config", load_config):
            yield
        os.unlink(file.name)

    def _assert_file(
        self,
        filename,
        opts=("--expand-star", "-m", "sqlalchemy"),
        encoding="utf-8",
        checkfile=None,
    ):

        with self._simulate_importlib(), self._capture_stdout() as buf:
            zimports.main(
                ["test_files/%s" % filename] + ["--stdout"] + list(opts)
            )

        if checkfile is None:
            checkfile = filename.replace(".py", ".expected.py")
        with open("test_files/%s" % checkfile, encoding=encoding) as file_:
            self.assertEqual(file_.read(), buf.getvalue())

    def setUp(self):
        self.mock_sqlalchemy = mock.MagicMock(
            **{name: mock.Mock() for name in sqlalchemy_names}
        )
        self.mock_sqlalchemy_orm = mock.MagicMock(
            __all__=sqlalchemy_orm_names,
            **{name: mock.Mock() for name in sqlalchemy_orm_names}
        )

    def test_star_imports_one(self):
        self._assert_file("star_imports.py")

    def test_star_imports_one_cryptography(self):
        self._assert_file(
            "star_imports.py",
            ["--style", "cryptography", "--expand-star", "-m", "sqlalchemy"],
            checkfile="star_imports.cryptography.expected.py",
        )

    def test_star_imports_two(self):
        self._assert_file("star_imports_two.py")

    def test_comment_inside_imports(self):
        self._assert_file("comment_inside_imports.py")

    def test_dupe_imports(self):
        self._assert_file("dupe_imports.py")

    def test_tricky_parens(self):
        self._assert_file("tricky_parens.py", ["-k"])

    def test_very_long_import(self):
        self._assert_file("very_long_import.py")

    def test_empty_file(self):
        self._assert_file("empty.py")

    def test_conditional_imports(self):
        self._assert_file("conditional_imports.py")

    def test_sqla_test_file(self):
        self._assert_file("sqla_test_file.py")

    def test_unused_rel_import(self):
        self._assert_file("unused_rel_import.py")

    def test_whitespace1(self):
        self._assert_file("whitespace1.py")

    def test_whitespace2(self):
        self._assert_file("whitespace2.py")

    def test_whitespace3(self):
        self._assert_file("whitespace3.py")

    def test_multiple_imports(self):
        self._assert_file("multi_imports.py", opts=("--multi-imports",))

    def test_unicode_characters(self):
        self._assert_file("unicode_characters.py")

    def test_magic_encoding_comment(self):
        self._assert_file("cp1252.py", encoding="cp1252")

    def test_per_file_ignore(self):
        with self._mock_config(
            """
[flake8]
per-file-ignores =
                 **/*.py:F401
                 lib/sqlalchemy/events.py:F401
        """
        ):
            self._assert_file("tricky_parens.py")

    def test_per_file_ignore_file_not_selected(self):
        with self._mock_config(
            """
[flake8]
per-file-ignores =
                 **/__init__.py:F401
                 lib/sqlalchemy/events.py:F401
        """
        ):
            self._assert_file(
                "tricky_parens.py", checkfile="tricky_parens.no_unused.py"
            )

    def test_per_file_ignore_other_codes(self):
        with self._mock_config(
            """
[flake8]
per-file-ignores =
                 **/*.py:E203,E305,E711,E712,E721,E722,E741
                 lib/sqlalchemy/events.py:F401
        """
        ):
            self._assert_file(
                "tricky_parens.py", checkfile="tricky_parens.no_unused.py"
            )


sqlalchemy_names = [
    "alias",
    "all_",
    "and_",
    "any_",
    "ARRAY",
    "asc",
    "between",
    "BIGINT",
    "BigInteger",
    "BINARY",
    "Binary",
    "bindparam",
    "BLANK_SCHEMA",
    "BLOB",
    "BOOLEAN",
    "Boolean",
    "case",
    "cast",
    "CHAR",
    "CheckConstraint",
    "CLOB",
    "collate",
    "Column",
    "column",
    "ColumnDefault",
    "Constraint",
    "create_engine",
    "DATE",
    "Date",
    "DATETIME",
    "DateTime",
    "DDL",
    "DECIMAL",
    "DefaultClause",
    "delete",
    "desc",
    "distinct",
    "engine_from_config",
    "Enum",
    "exc",
    "except_",
    "except_all",
    "exists",
    "extract",
    "false",
    "FetchedValue",
    "FLOAT",
    "Float",
    "ForeignKey",
    "ForeignKeyConstraint",
    "func",
    "funcfilter",
    "Index",
    "insert",
    "inspect",
    "INT",
    "INTEGER",
    "Integer",
    "intersect",
    "intersect_all",
    "Interval",
    "join",
    "JSON",
    "LargeBinary",
    "lateral",
    "literal",
    "literal_column",
    "MetaData",
    "modifier",
    "NCHAR",
    "not_",
    "null",
    "nullsfirst",
    "nullslast",
    "NUMERIC",
    "Numeric",
    "NVARCHAR",
    "or_",
    "outerjoin",
    "outparam",
    "over",
    "PassiveDefault",
    "PickleType",
    "PrimaryKeyConstraint",
    "REAL",
    "select",
    "Sequence",
    "SMALLINT",
    "SmallInteger",
    "String",
    "subquery",
    "Table",
    "table",
    "tablesample",
    "testing",
    "TEXT",
    "Text",
    "text",
    "ThreadLocalMetaData",
    "TIME",
    "Time",
    "TIMESTAMP",
    "true",
    "tuple_",
    "type_coerce",
    "TypeDecorator",
    "Unicode",
    "UnicodeText",
    "union",
    "union_all",
    "UniqueConstraint",
    "update",
    "util",
    "VARBINARY",
    "VARCHAR",
    "within_group",
]

sqlalchemy_orm_names = [
    "aliased",
    "AliasOption",
    "AttributeExtension",
    "attributes",
    "backref",
    "Bundle",
    "class_mapper",
    "clear_mappers",
    "column_property",
    "ColumnProperty",
    "comparable_property",
    "ComparableProperty",
    "compile_mappers",
    "composite",
    "CompositeProperty",
    "configure_mappers",
    "contains_alias",
    "contains_eager",
    "create_session",
    "defaultload",
    "defer",
    "deferred",
    "dynamic_loader",
    "eagerload",
    "eagerload_all",
    "EXT_CONTINUE",
    "EXT_SKIP",
    "EXT_STOP",
    "foreign",
    "immediateload",
    "join",
    "joinedload",
    "joinedload_all",
    "lazyload",
    "lazyload_all",
    "Load",
    "load_only",
    "make_transient",
    "make_transient_to_detached",
    "Mapper",
    "mapper",
    "MapperExtension",
    "noload",
    "object_mapper",
    "object_session",
    "outerjoin",
    "polymorphic_union",
    "PropComparator",
    "public_factory",
    "Query",
    "query_expression",
    "raiseload",
    "reconstructor",
    "relation",
    "relationship",
    "RelationshipProperty",
    "remote",
    "scoped_session",
    "selectin_polymorphic",
    "selectinload",
    "selectinload_all",
    "Session",
    "SessionExtension",
    "sessionmaker",
    "subqueryload",
    "subqueryload_all",
    "synonym",
    "SynonymProperty",
    "undefer",
    "undefer_group",
    "validates",
    "was_deleted",
    "with_expression",
    "with_parent",
    "with_polymorphic",
]
