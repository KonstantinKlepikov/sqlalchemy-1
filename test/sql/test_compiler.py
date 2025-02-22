#! coding:utf-8

"""
compiler tests.

These tests are among the very first that were written when SQLAlchemy
began in 2005.  As a result the testing style here is very dense;
it's an ongoing job to break these into much smaller tests with correct pep8
styling and coherent test organization.

"""

import decimal

from sqlalchemy import alias
from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import bindparam
from sqlalchemy import Boolean
from sqlalchemy import case
from sqlalchemy import cast
from sqlalchemy import CheckConstraint
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import desc
from sqlalchemy import distinct
from sqlalchemy import exc
from sqlalchemy import except_
from sqlalchemy import exists
from sqlalchemy import Float
from sqlalchemy import func
from sqlalchemy import Integer
from sqlalchemy import intersect
from sqlalchemy import join
from sqlalchemy import literal
from sqlalchemy import literal_column
from sqlalchemy import MetaData
from sqlalchemy import not_
from sqlalchemy import null
from sqlalchemy import Numeric
from sqlalchemy import or_
from sqlalchemy import outerjoin
from sqlalchemy import over
from sqlalchemy import schema
from sqlalchemy import select
from sqlalchemy import Sequence
from sqlalchemy import sql
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import testing
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy import TIMESTAMP
from sqlalchemy import true
from sqlalchemy import tuple_
from sqlalchemy import type_coerce
from sqlalchemy import types
from sqlalchemy import union
from sqlalchemy import union_all
from sqlalchemy import util
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects import oracle
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite
from sqlalchemy.dialects import sybase
from sqlalchemy.dialects.postgresql.base import PGCompiler
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.engine import default
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import column
from sqlalchemy.sql import compiler
from sqlalchemy.sql import label
from sqlalchemy.sql import table
from sqlalchemy.sql.expression import ClauseList
from sqlalchemy.sql.expression import HasPrefixes
from sqlalchemy.testing import assert_raises
from sqlalchemy.testing import assert_raises_message
from sqlalchemy.testing import AssertsCompiledSQL
from sqlalchemy.testing import eq_
from sqlalchemy.testing import eq_ignore_whitespace
from sqlalchemy.testing import fixtures
from sqlalchemy.testing import is_
from sqlalchemy.util import u


table1 = table(
    "mytable",
    column("myid", Integer),
    column("name", String),
    column("description", String),
)

table2 = table(
    "myothertable", column("otherid", Integer), column("othername", String)
)

table3 = table(
    "thirdtable", column("userid", Integer), column("otherstuff", String)
)

metadata = MetaData()

# table with a schema
table4 = Table(
    "remotetable",
    metadata,
    Column("rem_id", Integer, primary_key=True),
    Column("datatype_id", Integer),
    Column("value", String(20)),
    schema="remote_owner",
)

# table with a 'multipart' schema
table5 = Table(
    "remotetable",
    metadata,
    Column("rem_id", Integer, primary_key=True),
    Column("datatype_id", Integer),
    Column("value", String(20)),
    schema="dbo.remote_owner",
)

users = table(
    "users", column("user_id"), column("user_name"), column("password")
)

addresses = table(
    "addresses",
    column("address_id"),
    column("user_id"),
    column("street"),
    column("city"),
    column("state"),
    column("zip"),
)

keyed = Table(
    "keyed",
    metadata,
    Column("x", Integer, key="colx"),
    Column("y", Integer, key="coly"),
    Column("z", Integer),
)


class SelectTest(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = "default"

    def test_attribute_sanity(self):
        assert hasattr(table1, "c")
        assert hasattr(table1.select().subquery(), "c")
        assert not hasattr(table1.c.myid.self_group(), "columns")
        assert not hasattr(table1.c.myid, "columns")
        assert not hasattr(table1.c.myid, "c")
        assert not hasattr(table1.select().subquery().c.myid, "c")
        assert not hasattr(table1.select().subquery().c.myid, "columns")
        assert not hasattr(table1.alias().c.myid, "columns")
        assert not hasattr(table1.alias().c.myid, "c")
        with testing.expect_deprecated(
            "The SelectBase.c and SelectBase.columns attributes are "
            "deprecated"
        ):
            assert hasattr(table1.select(), "c")

        assert_raises_message(
            exc.InvalidRequestError,
            "Scalar Select expression has no "
            "columns; use this object directly within a "
            "column-level expression.",
            getattr,
            select([table1.c.myid]).scalar_subquery().self_group(),
            "columns",
        )

        assert_raises_message(
            exc.InvalidRequestError,
            "Scalar Select expression has no "
            "columns; use this object directly within a "
            "column-level expression.",
            getattr,
            select([table1.c.myid]).scalar_subquery(),
            "columns",
        )

    def test_prefix_constructor(self):
        class Pref(HasPrefixes):
            def _generate(self):
                return self

        assert_raises(
            exc.ArgumentError,
            Pref().prefix_with,
            "some prefix",
            not_a_dialect=True,
        )

    def test_table_select(self):
        self.assert_compile(
            table1.select(),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable",
        )

        self.assert_compile(
            select([table1, table2]),
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "myothertable.otherid, myothertable.othername FROM mytable, "
            "myothertable",
        )

    def test_invalid_col_argument(self):
        assert_raises(exc.ArgumentError, select, table1)
        assert_raises(exc.ArgumentError, select, table1.c.myid)

    def test_int_limit_offset_coercion(self):
        for given, exp in [
            ("5", 5),
            (5, 5),
            (5.2, 5),
            (decimal.Decimal("5"), 5),
            (None, None),
        ]:
            eq_(select().limit(given)._limit, exp)
            eq_(select().offset(given)._offset, exp)
            eq_(select(limit=given)._limit, exp)
            eq_(select(offset=given)._offset, exp)

        assert_raises(ValueError, select().limit, "foo")
        assert_raises(ValueError, select().offset, "foo")
        assert_raises(ValueError, select, offset="foo")
        assert_raises(ValueError, select, limit="foo")

    def test_limit_offset_no_int_coercion_one(self):
        exp1 = literal_column("Q")
        exp2 = literal_column("Y")
        self.assert_compile(
            select([1]).limit(exp1).offset(exp2), "SELECT 1 LIMIT Q OFFSET Y"
        )

        self.assert_compile(
            select([1]).limit(bindparam("x")).offset(bindparam("y")),
            "SELECT 1 LIMIT :x OFFSET :y",
        )

    def test_limit_offset_no_int_coercion_two(self):
        exp1 = literal_column("Q")
        exp2 = literal_column("Y")
        sel = select([1]).limit(exp1).offset(exp2)

        assert_raises_message(
            exc.CompileError,
            "This SELECT structure does not use a simple integer "
            "value for limit",
            getattr,
            sel,
            "_limit",
        )

        assert_raises_message(
            exc.CompileError,
            "This SELECT structure does not use a simple integer "
            "value for offset",
            getattr,
            sel,
            "_offset",
        )

    def test_limit_offset_no_int_coercion_three(self):
        exp1 = bindparam("Q")
        exp2 = bindparam("Y")
        sel = select([1]).limit(exp1).offset(exp2)

        assert_raises_message(
            exc.CompileError,
            "This SELECT structure does not use a simple integer "
            "value for limit",
            getattr,
            sel,
            "_limit",
        )

        assert_raises_message(
            exc.CompileError,
            "This SELECT structure does not use a simple integer "
            "value for offset",
            getattr,
            sel,
            "_offset",
        )

    def test_limit_offset(self):
        for lim, offset, exp, params in [
            (
                5,
                10,
                "LIMIT :param_1 OFFSET :param_2",
                {"param_1": 5, "param_2": 10},
            ),
            (None, 10, "LIMIT -1 OFFSET :param_1", {"param_1": 10}),
            (5, None, "LIMIT :param_1", {"param_1": 5}),
            (
                0,
                0,
                "LIMIT :param_1 OFFSET :param_2",
                {"param_1": 0, "param_2": 0},
            ),
        ]:
            self.assert_compile(
                select([1]).limit(lim).offset(offset),
                "SELECT 1 " + exp,
                checkparams=params,
            )

    def test_select_precol_compile_ordering(self):
        s1 = (
            select([column("x")])
            .select_from(text("a"))
            .limit(5)
            .scalar_subquery()
        )
        s2 = select([s1]).limit(10)

        class MyCompiler(compiler.SQLCompiler):
            def get_select_precolumns(self, select, **kw):
                result = ""
                if select._limit:
                    result += "FIRST %s " % self.process(
                        literal(select._limit), **kw
                    )
                if select._offset:
                    result += "SKIP %s " % self.process(
                        literal(select._offset), **kw
                    )
                return result

            def limit_clause(self, select, **kw):
                return ""

        dialect = default.DefaultDialect()
        dialect.statement_compiler = MyCompiler
        dialect.paramstyle = "qmark"
        dialect.positional = True
        self.assert_compile(
            s2,
            "SELECT FIRST ? (SELECT FIRST ? x FROM a) AS anon_1",
            checkpositional=(10, 5),
            dialect=dialect,
        )

    def test_from_subquery(self):
        """tests placing select statements in the column clause of
        another select, for the
        purposes of selecting from the exported columns of that select."""

        s = select([table1], table1.c.name == "jack").subquery()
        self.assert_compile(
            select([s], s.c.myid == 7),
            "SELECT anon_1.myid, anon_1.name, anon_1.description FROM "
            "(SELECT mytable.myid AS myid, "
            "mytable.name AS name, mytable.description AS description "
            "FROM mytable "
            "WHERE mytable.name = :name_1) AS anon_1 WHERE "
            "anon_1.myid = :myid_1",
        )

        sq = select([table1])
        self.assert_compile(
            sq.subquery().select(),
            "SELECT anon_1.myid, anon_1.name, anon_1.description FROM "
            "(SELECT mytable.myid AS myid, "
            "mytable.name AS name, mytable.description "
            "AS description FROM mytable) AS anon_1",
        )

        sq = select([table1]).alias("sq")

        self.assert_compile(
            sq.select(sq.c.myid == 7),
            "SELECT sq.myid, sq.name, sq.description FROM "
            "(SELECT mytable.myid AS myid, mytable.name AS name, "
            "mytable.description AS description FROM mytable) AS sq "
            "WHERE sq.myid = :myid_1",
        )

        sq = select(
            [table1, table2],
            and_(table1.c.myid == 7, table2.c.otherid == table1.c.myid),
            use_labels=True,
        ).alias("sq")

        sqstring = (
            "SELECT mytable.myid AS mytable_myid, mytable.name AS "
            "mytable_name, mytable.description AS mytable_description, "
            "myothertable.otherid AS myothertable_otherid, "
            "myothertable.othername AS myothertable_othername FROM "
            "mytable, myothertable WHERE mytable.myid = :myid_1 AND "
            "myothertable.otherid = mytable.myid"
        )

        self.assert_compile(
            sq.select(),
            "SELECT sq.mytable_myid, sq.mytable_name, "
            "sq.mytable_description, sq.myothertable_otherid, "
            "sq.myothertable_othername FROM (%s) AS sq" % sqstring,
        )

        sq2 = select([sq], use_labels=True).alias("sq2")

        self.assert_compile(
            sq2.select(),
            "SELECT sq2.sq_mytable_myid, sq2.sq_mytable_name, "
            "sq2.sq_mytable_description, sq2.sq_myothertable_otherid, "
            "sq2.sq_myothertable_othername FROM "
            "(SELECT sq.mytable_myid AS "
            "sq_mytable_myid, sq.mytable_name AS sq_mytable_name, "
            "sq.mytable_description AS sq_mytable_description, "
            "sq.myothertable_otherid AS sq_myothertable_otherid, "
            "sq.myothertable_othername AS sq_myothertable_othername "
            "FROM (%s) AS sq) AS sq2" % sqstring,
        )

    def test_select_from_clauselist(self):
        self.assert_compile(
            select([ClauseList(column("a"), column("b"))]).select_from(
                text("sometable")
            ),
            "SELECT a, b FROM sometable",
        )

    def test_use_labels(self):
        self.assert_compile(
            select([table1.c.myid == 5], use_labels=True),
            "SELECT mytable.myid = :myid_1 AS anon_1 FROM mytable",
        )

        self.assert_compile(
            select([func.foo()], use_labels=True), "SELECT foo() AS foo_1"
        )

        # this is native_boolean=False for default dialect
        self.assert_compile(
            select([not_(True)], use_labels=True),
            "SELECT :param_1 = 0 AS anon_1",
        )

        self.assert_compile(
            select([cast("data", Integer)], use_labels=True),
            "SELECT CAST(:param_1 AS INTEGER) AS anon_1",
        )

        self.assert_compile(
            select(
                [func.sum(func.lala(table1.c.myid).label("foo")).label("bar")]
            ),
            "SELECT sum(lala(mytable.myid)) AS bar FROM mytable",
        )

        self.assert_compile(
            select([keyed]), "SELECT keyed.x, keyed.y" ", keyed.z FROM keyed"
        )

        self.assert_compile(
            select([keyed]).apply_labels(),
            "SELECT keyed.x AS keyed_x, keyed.y AS "
            "keyed_y, keyed.z AS keyed_z FROM keyed",
        )

        self.assert_compile(
            select([select([keyed]).apply_labels().subquery()]).apply_labels(),
            "SELECT anon_1.keyed_x AS anon_1_keyed_x, "
            "anon_1.keyed_y AS anon_1_keyed_y, "
            "anon_1.keyed_z AS anon_1_keyed_z "
            "FROM (SELECT keyed.x AS keyed_x, keyed.y AS keyed_y, "
            "keyed.z AS keyed_z FROM keyed) AS anon_1",
        )

    def test_paramstyles(self):
        stmt = text("select :foo, :bar, :bat from sometable")

        self.assert_compile(
            stmt,
            "select ?, ?, ? from sometable",
            dialect=default.DefaultDialect(paramstyle="qmark"),
        )
        self.assert_compile(
            stmt,
            "select :foo, :bar, :bat from sometable",
            dialect=default.DefaultDialect(paramstyle="named"),
        )
        self.assert_compile(
            stmt,
            "select %s, %s, %s from sometable",
            dialect=default.DefaultDialect(paramstyle="format"),
        )
        self.assert_compile(
            stmt,
            "select :1, :2, :3 from sometable",
            dialect=default.DefaultDialect(paramstyle="numeric"),
        )
        self.assert_compile(
            stmt,
            "select %(foo)s, %(bar)s, %(bat)s from sometable",
            dialect=default.DefaultDialect(paramstyle="pyformat"),
        )

    def test_anon_param_name_on_keys(self):
        self.assert_compile(
            keyed.insert(),
            "INSERT INTO keyed (x, y, z) VALUES (%(colx)s, %(coly)s, %(z)s)",
            dialect=default.DefaultDialect(paramstyle="pyformat"),
        )
        self.assert_compile(
            keyed.c.coly == 5,
            "keyed.y = %(coly_1)s",
            checkparams={"coly_1": 5},
            dialect=default.DefaultDialect(paramstyle="pyformat"),
        )

    def test_dupe_columns(self):
        """as of 1.4, there's no deduping."""

        self.assert_compile(
            select([column("a"), column("a"), column("a")]),
            "SELECT a, a, a",
            dialect=default.DefaultDialect(),
        )

        c = column("a")
        self.assert_compile(
            select([c, c, c]),
            "SELECT a, a, a",
            dialect=default.DefaultDialect(),
        )

        a, b = column("a"), column("b")
        self.assert_compile(
            select([a, b, b, b, a, a]),
            "SELECT a, b, b, b, a, a",
            dialect=default.DefaultDialect(),
        )

        # using alternate keys.
        a, b, c = (
            Column("a", Integer, key="b"),
            Column("b", Integer),
            Column("c", Integer, key="a"),
        )
        self.assert_compile(
            select([a, b, c, a, b, c]),
            "SELECT a, b, c, a, b, c",
            dialect=default.DefaultDialect(),
        )

        self.assert_compile(
            select([bindparam("a"), bindparam("b"), bindparam("c")]),
            "SELECT :a AS anon_1, :b AS anon_2, :c AS anon_3",
            dialect=default.DefaultDialect(paramstyle="named"),
        )

        self.assert_compile(
            select([bindparam("a"), bindparam("b"), bindparam("c")]),
            "SELECT ? AS anon_1, ? AS anon_2, ? AS anon_3",
            dialect=default.DefaultDialect(paramstyle="qmark"),
        )

        self.assert_compile(
            select([column("a"), column("a"), column("a")]), "SELECT a, a, a"
        )

        s = select([bindparam("a"), bindparam("b"), bindparam("c")])
        s = s.compile(dialect=default.DefaultDialect(paramstyle="qmark"))
        eq_(s.positiontup, ["a", "b", "c"])

    def test_dupe_columns_use_labels(self):
        """as of 1.4, there's no deduping.

        however the labels will still uniqify themselves...
        """

        t = table("t", column("a"), column("b"))
        self.assert_compile(
            select([t.c.a, t.c.a, t.c.b]).apply_labels(),
            "SELECT t.a AS t_a, t.a AS t_a_1, t.b AS t_b FROM t",
        )

    def test_nested_label_targeting(self):
        """test nested anonymous label generation.

        """
        s1 = table1.select()
        s2 = s1.alias()
        s3 = select([s2], use_labels=True)
        s4 = s3.alias()
        s5 = select([s4], use_labels=True)
        self.assert_compile(
            s5,
            "SELECT anon_1.anon_2_myid AS "
            "anon_1_anon_2_myid, anon_1.anon_2_name AS "
            "anon_1_anon_2_name, anon_1.anon_2_descript"
            "ion AS anon_1_anon_2_description FROM "
            "(SELECT anon_2.myid AS anon_2_myid, "
            "anon_2.name AS anon_2_name, "
            "anon_2.description AS anon_2_description "
            "FROM (SELECT mytable.myid AS myid, "
            "mytable.name AS name, mytable.description "
            "AS description FROM mytable) AS anon_2) "
            "AS anon_1",
        )

    def test_nested_label_targeting_keyed(self):
        s1 = keyed.select()
        s2 = s1.alias()
        s3 = select([s2], use_labels=True)
        self.assert_compile(
            s3,
            "SELECT anon_1.x AS anon_1_x, "
            "anon_1.y AS anon_1_y, "
            "anon_1.z AS anon_1_z FROM "
            "(SELECT keyed.x AS x, keyed.y "
            "AS y, keyed.z AS z FROM keyed) AS anon_1",
        )

        s4 = s3.alias()
        s5 = select([s4], use_labels=True)
        self.assert_compile(
            s5,
            "SELECT anon_1.anon_2_x AS anon_1_anon_2_x, "
            "anon_1.anon_2_y AS anon_1_anon_2_y, "
            "anon_1.anon_2_z AS anon_1_anon_2_z "
            "FROM (SELECT anon_2.x AS anon_2_x, "
            "anon_2.y AS anon_2_y, "
            "anon_2.z AS anon_2_z FROM "
            "(SELECT keyed.x AS x, keyed.y AS y, keyed.z "
            "AS z FROM keyed) AS anon_2) AS anon_1",
        )

    def test_exists(self):
        s = select([table1.c.myid]).where(table1.c.myid == 5)

        self.assert_compile(
            exists(s),
            "EXISTS (SELECT mytable.myid FROM mytable "
            "WHERE mytable.myid = :myid_1)",
        )

        self.assert_compile(
            exists(s.scalar_subquery()),
            "EXISTS (SELECT mytable.myid FROM mytable "
            "WHERE mytable.myid = :myid_1)",
        )

        self.assert_compile(
            exists([table1.c.myid], table1.c.myid == 5).select(),
            "SELECT EXISTS (SELECT mytable.myid FROM "
            "mytable WHERE mytable.myid = :myid_1) AS anon_1",
            params={"mytable_myid": 5},
        )
        self.assert_compile(
            select([table1, exists([1], from_obj=table2)]),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description, EXISTS (SELECT 1 "
            "FROM myothertable) AS anon_1 FROM mytable",
            params={},
        )
        self.assert_compile(
            select([table1, exists([1], from_obj=table2).label("foo")]),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description, EXISTS (SELECT 1 "
            "FROM myothertable) AS foo FROM mytable",
            params={},
        )

        self.assert_compile(
            table1.select(
                exists()
                .where(table2.c.otherid == table1.c.myid)
                .correlate(table1)
            ),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable WHERE "
            "EXISTS (SELECT * FROM myothertable WHERE "
            "myothertable.otherid = mytable.myid)",
        )
        self.assert_compile(
            table1.select(
                exists()
                .where(table2.c.otherid == table1.c.myid)
                .correlate(table1)
            ),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable WHERE "
            "EXISTS (SELECT * FROM myothertable WHERE "
            "myothertable.otherid = mytable.myid)",
        )

        self.assert_compile(
            select(
                [
                    or_(
                        exists().where(table2.c.otherid == "foo"),
                        exists().where(table2.c.otherid == "bar"),
                    )
                ]
            ),
            "SELECT (EXISTS (SELECT * FROM myothertable "
            "WHERE myothertable.otherid = :otherid_1)) "
            "OR (EXISTS (SELECT * FROM myothertable WHERE "
            "myothertable.otherid = :otherid_2)) AS anon_1",
        )

        self.assert_compile(
            select([exists([1])]), "SELECT EXISTS (SELECT 1) AS anon_1"
        )

        self.assert_compile(
            select([~exists([1])]), "SELECT NOT (EXISTS (SELECT 1)) AS anon_1"
        )

        self.assert_compile(
            select([~(~exists([1]))]),
            "SELECT NOT (NOT (EXISTS (SELECT 1))) AS anon_1",
        )

    def test_where_subquery(self):
        s = select(
            [addresses.c.street],
            addresses.c.user_id == users.c.user_id,
            correlate=True,
        ).alias("s")

        # don't correlate in a FROM list
        self.assert_compile(
            select([users, s.c.street], from_obj=s),
            "SELECT users.user_id, users.user_name, "
            "users.password, s.street FROM users, "
            "(SELECT addresses.street AS street FROM "
            "addresses, users WHERE addresses.user_id = "
            "users.user_id) AS s",
        )
        self.assert_compile(
            table1.select(
                table1.c.myid
                == select(
                    [table1.c.myid], table1.c.name == "jack"
                ).scalar_subquery()
            ),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable WHERE "
            "mytable.myid = (SELECT mytable.myid FROM "
            "mytable WHERE mytable.name = :name_1)",
        )
        self.assert_compile(
            table1.select(
                table1.c.myid
                == select(
                    [table2.c.otherid], table1.c.name == table2.c.othername
                ).scalar_subquery()
            ),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable WHERE "
            "mytable.myid = (SELECT "
            "myothertable.otherid FROM myothertable "
            "WHERE mytable.name = myothertable.othernam"
            "e)",
        )
        self.assert_compile(
            table1.select(exists([1], table2.c.otherid == table1.c.myid)),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable WHERE "
            "EXISTS (SELECT 1 FROM myothertable WHERE "
            "myothertable.otherid = mytable.myid)",
        )
        talias = table1.alias("ta")
        s = select(
            [talias], exists([1], table2.c.otherid == talias.c.myid)
        ).subquery("sq2")
        self.assert_compile(
            select([s, table1]),
            "SELECT sq2.myid, sq2.name, "
            "sq2.description, mytable.myid, "
            "mytable.name, mytable.description FROM "
            "(SELECT ta.myid AS myid, ta.name AS name, "
            "ta.description AS description FROM "
            "mytable AS ta WHERE EXISTS (SELECT 1 FROM "
            "myothertable WHERE myothertable.otherid = "
            "ta.myid)) AS sq2, mytable",
        )

        # test constructing the outer query via append_column(), which
        # occurs in the ORM's Query object

        s = select(
            [], exists([1], table2.c.otherid == table1.c.myid), from_obj=table1
        )
        s.column.non_generative(s, table1)
        self.assert_compile(
            s,
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable WHERE "
            "EXISTS (SELECT 1 FROM myothertable WHERE "
            "myothertable.otherid = mytable.myid)",
        )

    def test_orderby_subquery(self):
        self.assert_compile(
            table1.select().order_by(
                select(
                    [table2.c.otherid], table1.c.myid == table2.c.otherid
                ).scalar_subquery()
            ),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable ORDER BY "
            "(SELECT myothertable.otherid FROM "
            "myothertable WHERE mytable.myid = "
            "myothertable.otherid)",
        )
        self.assert_compile(
            table1.select().order_by(
                desc(
                    select(
                        [table2.c.otherid], table1.c.myid == table2.c.otherid
                    ).scalar_subquery()
                )
            ),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable ORDER BY "
            "(SELECT myothertable.otherid FROM "
            "myothertable WHERE mytable.myid = "
            "myothertable.otherid) DESC",
        )

    def test_scalar_select(self):
        s = select([table1.c.myid], correlate=False).scalar_subquery()
        self.assert_compile(
            select([table1, s]),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description, (SELECT mytable.myid "
            "FROM mytable) AS anon_1 FROM mytable",
        )
        s = select([table1.c.myid]).scalar_subquery()
        self.assert_compile(
            select([table2, s]),
            "SELECT myothertable.otherid, "
            "myothertable.othername, (SELECT "
            "mytable.myid FROM mytable) AS anon_1 FROM "
            "myothertable",
        )
        s = select([table1.c.myid]).correlate(None).scalar_subquery()
        self.assert_compile(
            select([table1, s]),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description, (SELECT mytable.myid "
            "FROM mytable) AS anon_1 FROM mytable",
        )

        s = select([table1.c.myid]).scalar_subquery()
        s2 = s.where(table1.c.myid == 5)
        self.assert_compile(
            s2,
            "(SELECT mytable.myid FROM mytable WHERE mytable.myid = :myid_1)",
        )
        self.assert_compile(s, "(SELECT mytable.myid FROM mytable)")
        # test that aliases use scalar_subquery() when used in an explicitly
        # scalar context

        s = select([table1.c.myid]).scalar_subquery()
        self.assert_compile(
            select([table1.c.myid]).where(table1.c.myid == s),
            "SELECT mytable.myid FROM mytable WHERE "
            "mytable.myid = (SELECT mytable.myid FROM "
            "mytable)",
        )
        self.assert_compile(
            select([table1.c.myid]).where(table1.c.myid < s),
            "SELECT mytable.myid FROM mytable WHERE "
            "mytable.myid < (SELECT mytable.myid FROM "
            "mytable)",
        )
        s = select([table1.c.myid]).scalar_subquery()
        self.assert_compile(
            select([table2, s]),
            "SELECT myothertable.otherid, "
            "myothertable.othername, (SELECT "
            "mytable.myid FROM mytable) AS anon_1 FROM "
            "myothertable",
        )

        # test expressions against scalar selects

        self.assert_compile(
            select([s - literal(8)]),
            "SELECT (SELECT mytable.myid FROM mytable) "
            "- :param_1 AS anon_1",
        )
        self.assert_compile(
            select([select([table1.c.name]).scalar_subquery() + literal("x")]),
            "SELECT (SELECT mytable.name FROM mytable) "
            "|| :param_1 AS anon_1",
        )
        self.assert_compile(
            select([s > literal(8)]),
            "SELECT (SELECT mytable.myid FROM mytable) "
            "> :param_1 AS anon_1",
        )
        self.assert_compile(
            select([select([table1.c.name]).label("foo")]),
            "SELECT (SELECT mytable.name FROM mytable) " "AS foo",
        )

        # scalar selects should not have any attributes on their 'c' or
        # 'columns' attribute

        s = select([table1.c.myid]).scalar_subquery()
        assert_raises_message(
            exc.InvalidRequestError,
            "Scalar Select expression has no columns; use this "
            "object directly within a column-level expression.",
            lambda: s.c.foo,
        )
        assert_raises_message(
            exc.InvalidRequestError,
            "Scalar Select expression has no columns; use this "
            "object directly within a column-level expression.",
            lambda: s.columns.foo,
        )

        zips = table(
            "zips", column("zipcode"), column("latitude"), column("longitude")
        )
        places = table("places", column("id"), column("nm"))
        zipcode = "12345"
        qlat = (
            select([zips.c.latitude], zips.c.zipcode == zipcode)
            .correlate(None)
            .scalar_subquery()
        )
        qlng = (
            select([zips.c.longitude], zips.c.zipcode == zipcode)
            .correlate(None)
            .scalar_subquery()
        )

        q = select(
            [
                places.c.id,
                places.c.nm,
                zips.c.zipcode,
                func.latlondist(qlat, qlng).label("dist"),
            ],
            zips.c.zipcode == zipcode,
            order_by=["dist", places.c.nm],
        )

        self.assert_compile(
            q,
            "SELECT places.id, places.nm, "
            "zips.zipcode, latlondist((SELECT "
            "zips.latitude FROM zips WHERE "
            "zips.zipcode = :zipcode_1), (SELECT "
            "zips.longitude FROM zips WHERE "
            "zips.zipcode = :zipcode_2)) AS dist FROM "
            "places, zips WHERE zips.zipcode = "
            ":zipcode_3 ORDER BY dist, places.nm",
        )

        zalias = zips.alias("main_zip")
        qlat = select(
            [zips.c.latitude], zips.c.zipcode == zalias.c.zipcode
        ).scalar_subquery()
        qlng = select(
            [zips.c.longitude], zips.c.zipcode == zalias.c.zipcode
        ).scalar_subquery()
        q = select(
            [
                places.c.id,
                places.c.nm,
                zalias.c.zipcode,
                func.latlondist(qlat, qlng).label("dist"),
            ],
            order_by=["dist", places.c.nm],
        )
        self.assert_compile(
            q,
            "SELECT places.id, places.nm, "
            "main_zip.zipcode, latlondist((SELECT "
            "zips.latitude FROM zips WHERE "
            "zips.zipcode = main_zip.zipcode), (SELECT "
            "zips.longitude FROM zips WHERE "
            "zips.zipcode = main_zip.zipcode)) AS dist "
            "FROM places, zips AS main_zip ORDER BY "
            "dist, places.nm",
        )

        a1 = table2.alias("t2alias")
        s1 = select(
            [a1.c.otherid], table1.c.myid == a1.c.otherid
        ).scalar_subquery()
        j1 = table1.join(table2, table1.c.myid == table2.c.otherid)
        s2 = select([table1, s1], from_obj=j1)
        self.assert_compile(
            s2,
            "SELECT mytable.myid, mytable.name, "
            "mytable.description, (SELECT "
            "t2alias.otherid FROM myothertable AS "
            "t2alias WHERE mytable.myid = "
            "t2alias.otherid) AS anon_1 FROM mytable "
            "JOIN myothertable ON mytable.myid = "
            "myothertable.otherid",
        )

    def test_label_comparison_one(self):
        x = func.lala(table1.c.myid).label("foo")
        self.assert_compile(
            select([x], x == 5),
            "SELECT lala(mytable.myid) AS foo FROM "
            "mytable WHERE lala(mytable.myid) = "
            ":param_1",
        )

    def test_label_comparison_two(self):
        self.assert_compile(
            label("bar", column("foo", type_=String)) + "foo",
            "foo || :param_1",
        )

    def test_order_by_labels_enabled(self):
        lab1 = (table1.c.myid + 12).label("foo")
        lab2 = func.somefunc(table1.c.name).label("bar")
        dialect = default.DefaultDialect()

        self.assert_compile(
            select([lab1, lab2]).order_by(lab1, desc(lab2)),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY foo, bar DESC",
            dialect=dialect,
        )

        # the function embedded label renders as the function
        self.assert_compile(
            select([lab1, lab2]).order_by(func.hoho(lab1), desc(lab2)),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY hoho(mytable.myid + :myid_1), bar DESC",
            dialect=dialect,
        )

        # binary expressions render as the expression without labels
        self.assert_compile(
            select([lab1, lab2]).order_by(lab1 + "test"),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY mytable.myid + :myid_1 + :param_1",
            dialect=dialect,
        )

        # labels within functions in the columns clause render
        # with the expression
        self.assert_compile(
            select([lab1, func.foo(lab1)]).order_by(lab1, func.foo(lab1)),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "foo(mytable.myid + :myid_1) AS foo_1 FROM mytable "
            "ORDER BY foo, foo(mytable.myid + :myid_1)",
            dialect=dialect,
        )

        lx = (table1.c.myid + table1.c.myid).label("lx")
        ly = (func.lower(table1.c.name) + table1.c.description).label("ly")

        self.assert_compile(
            select([lx, ly]).order_by(lx, ly.desc()),
            "SELECT mytable.myid + mytable.myid AS lx, "
            "lower(mytable.name) || mytable.description AS ly "
            "FROM mytable ORDER BY lx, ly DESC",
            dialect=dialect,
        )

        # expression isn't actually the same thing (even though label is)
        self.assert_compile(
            select([lab1, lab2]).order_by(
                table1.c.myid.label("foo"), desc(table1.c.name.label("bar"))
            ),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY mytable.myid, mytable.name DESC",
            dialect=dialect,
        )

        # it's also an exact match, not aliased etc.
        self.assert_compile(
            select([lab1, lab2]).order_by(
                desc(table1.alias().c.name.label("bar"))
            ),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY mytable_1.name DESC",
            dialect=dialect,
        )

        # but! it's based on lineage
        lab2_lineage = lab2.element._clone()
        self.assert_compile(
            select([lab1, lab2]).order_by(desc(lab2_lineage.label("bar"))),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY bar DESC",
            dialect=dialect,
        )

        # here, 'name' is implicitly available, but w/ #3882 we don't
        # want to render a name that isn't specifically a Label elsewhere
        # in the query
        self.assert_compile(
            select([table1.c.myid]).order_by(table1.c.name.label("name")),
            "SELECT mytable.myid FROM mytable ORDER BY mytable.name",
        )

        # as well as if it doesn't match
        self.assert_compile(
            select([table1.c.myid]).order_by(
                func.lower(table1.c.name).label("name")
            ),
            "SELECT mytable.myid FROM mytable ORDER BY lower(mytable.name)",
        )

    def test_order_by_labels_disabled(self):
        lab1 = (table1.c.myid + 12).label("foo")
        lab2 = func.somefunc(table1.c.name).label("bar")
        dialect = default.DefaultDialect()
        dialect.supports_simple_order_by_label = False
        self.assert_compile(
            select([lab1, lab2]).order_by(lab1, desc(lab2)),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY mytable.myid + :myid_1, somefunc(mytable.name) DESC",
            dialect=dialect,
        )
        self.assert_compile(
            select([lab1, lab2]).order_by(func.hoho(lab1), desc(lab2)),
            "SELECT mytable.myid + :myid_1 AS foo, "
            "somefunc(mytable.name) AS bar FROM mytable "
            "ORDER BY hoho(mytable.myid + :myid_1), "
            "somefunc(mytable.name) DESC",
            dialect=dialect,
        )

    def test_no_group_by_labels(self):
        lab1 = (table1.c.myid + 12).label("foo")
        lab2 = func.somefunc(table1.c.name).label("bar")
        dialect = default.DefaultDialect()

        self.assert_compile(
            select([lab1, lab2]).group_by(lab1, lab2),
            "SELECT mytable.myid + :myid_1 AS foo, somefunc(mytable.name) "
            "AS bar FROM mytable GROUP BY mytable.myid + :myid_1, "
            "somefunc(mytable.name)",
            dialect=dialect,
        )

    def test_conjunctions(self):
        a, b, c = text("a"), text("b"), text("c")
        x = and_(a, b, c)
        assert isinstance(x.type, Boolean)
        assert str(x) == "a AND b AND c"
        self.assert_compile(
            select([x.label("foo")]), "SELECT a AND b AND c AS foo"
        )

        self.assert_compile(
            and_(
                table1.c.myid == 12,
                table1.c.name == "asdf",
                table2.c.othername == "foo",
                text("sysdate() = today()"),
            ),
            "mytable.myid = :myid_1 AND mytable.name = :name_1 "
            "AND myothertable.othername = "
            ":othername_1 AND sysdate() = today()",
        )

        self.assert_compile(
            and_(
                table1.c.myid == 12,
                or_(
                    table2.c.othername == "asdf",
                    table2.c.othername == "foo",
                    table2.c.otherid == 9,
                ),
                text("sysdate() = today()"),
            ),
            "mytable.myid = :myid_1 AND (myothertable.othername = "
            ":othername_1 OR myothertable.othername = :othername_2 OR "
            "myothertable.otherid = :otherid_1) AND sysdate() = "
            "today()",
            checkparams={
                "othername_1": "asdf",
                "othername_2": "foo",
                "otherid_1": 9,
                "myid_1": 12,
            },
        )

        # test a generator
        self.assert_compile(
            and_(
                conj for conj in [table1.c.myid == 12, table1.c.name == "asdf"]
            ),
            "mytable.myid = :myid_1 AND mytable.name = :name_1",
        )

    def test_nested_conjunctions_short_circuit(self):
        """test that empty or_(), and_() conjunctions are collapsed by
        an enclosing conjunction."""

        t = table("t", column("x"))

        self.assert_compile(
            select([t]).where(and_(t.c.x == 5, or_(and_(or_(t.c.x == 7))))),
            "SELECT t.x FROM t WHERE t.x = :x_1 AND t.x = :x_2",
        )
        self.assert_compile(
            select([t]).where(and_(or_(t.c.x == 12, and_(or_(t.c.x == 8))))),
            "SELECT t.x FROM t WHERE t.x = :x_1 OR t.x = :x_2",
        )
        self.assert_compile(
            select([t]).where(
                and_(
                    or_(
                        or_(t.c.x == 12),
                        and_(or_(), or_(and_(t.c.x == 8)), and_()),
                    )
                )
            ),
            "SELECT t.x FROM t WHERE t.x = :x_1 OR t.x = :x_2",
        )

    def test_true_short_circuit(self):
        t = table("t", column("x"))

        self.assert_compile(
            select([t]).where(true()),
            "SELECT t.x FROM t WHERE 1 = 1",
            dialect=default.DefaultDialect(supports_native_boolean=False),
        )
        self.assert_compile(
            select([t]).where(true()),
            "SELECT t.x FROM t WHERE true",
            dialect=default.DefaultDialect(supports_native_boolean=True),
        )

        self.assert_compile(
            select([t]),
            "SELECT t.x FROM t",
            dialect=default.DefaultDialect(supports_native_boolean=True),
        )

    def test_distinct(self):
        self.assert_compile(
            select([table1.c.myid.distinct()]),
            "SELECT DISTINCT mytable.myid FROM mytable",
        )

        self.assert_compile(
            select([distinct(table1.c.myid)]),
            "SELECT DISTINCT mytable.myid FROM mytable",
        )

        self.assert_compile(
            select([table1.c.myid]).distinct(),
            "SELECT DISTINCT mytable.myid FROM mytable",
        )

        self.assert_compile(
            select([func.count(table1.c.myid.distinct())]),
            "SELECT count(DISTINCT mytable.myid) AS count_1 FROM mytable",
        )

        self.assert_compile(
            select([func.count(distinct(table1.c.myid))]),
            "SELECT count(DISTINCT mytable.myid) AS count_1 FROM mytable",
        )

    def test_where_empty(self):
        self.assert_compile(
            select([table1.c.myid]).where(and_()),
            "SELECT mytable.myid FROM mytable",
        )
        self.assert_compile(
            select([table1.c.myid]).where(or_()),
            "SELECT mytable.myid FROM mytable",
        )

    def test_order_by_nulls(self):
        self.assert_compile(
            table2.select(
                order_by=[
                    table2.c.otherid,
                    table2.c.othername.desc().nullsfirst(),
                ]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid, "
            "myothertable.othername DESC NULLS FIRST",
        )

        self.assert_compile(
            table2.select(
                order_by=[
                    table2.c.otherid,
                    table2.c.othername.desc().nullslast(),
                ]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid, "
            "myothertable.othername DESC NULLS LAST",
        )

        self.assert_compile(
            table2.select(
                order_by=[
                    table2.c.otherid.nullslast(),
                    table2.c.othername.desc().nullsfirst(),
                ]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid NULLS LAST, "
            "myothertable.othername DESC NULLS FIRST",
        )

        self.assert_compile(
            table2.select(
                order_by=[
                    table2.c.otherid.nullsfirst(),
                    table2.c.othername.desc(),
                ]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid NULLS FIRST, "
            "myothertable.othername DESC",
        )

        self.assert_compile(
            table2.select(
                order_by=[
                    table2.c.otherid.nullsfirst(),
                    table2.c.othername.desc().nullslast(),
                ]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid NULLS FIRST, "
            "myothertable.othername DESC NULLS LAST",
        )

    def test_orderby_groupby(self):
        self.assert_compile(
            table2.select(
                order_by=[table2.c.otherid, asc(table2.c.othername)]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid, "
            "myothertable.othername ASC",
        )

        self.assert_compile(
            table2.select(
                order_by=[table2.c.otherid, table2.c.othername.desc()]
            ),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid, "
            "myothertable.othername DESC",
        )

        # generative order_by
        self.assert_compile(
            table2.select()
            .order_by(table2.c.otherid)
            .order_by(table2.c.othername.desc()),
            "SELECT myothertable.otherid, myothertable.othername FROM "
            "myothertable ORDER BY myothertable.otherid, "
            "myothertable.othername DESC",
        )

        self.assert_compile(
            table2.select()
            .order_by(table2.c.otherid)
            .order_by(table2.c.othername.desc())
            .order_by(None),
            "SELECT myothertable.otherid, myothertable.othername "
            "FROM myothertable",
        )

        self.assert_compile(
            select(
                [table2.c.othername, func.count(table2.c.otherid)],
                group_by=[table2.c.othername],
            ),
            "SELECT myothertable.othername, "
            "count(myothertable.otherid) AS count_1 "
            "FROM myothertable GROUP BY myothertable.othername",
        )

        # generative group by
        self.assert_compile(
            select(
                [table2.c.othername, func.count(table2.c.otherid)]
            ).group_by(table2.c.othername),
            "SELECT myothertable.othername, "
            "count(myothertable.otherid) AS count_1 "
            "FROM myothertable GROUP BY myothertable.othername",
        )

        self.assert_compile(
            select([table2.c.othername, func.count(table2.c.otherid)])
            .group_by(table2.c.othername)
            .group_by(None),
            "SELECT myothertable.othername, "
            "count(myothertable.otherid) AS count_1 "
            "FROM myothertable",
        )

        self.assert_compile(
            select(
                [table2.c.othername, func.count(table2.c.otherid)],
                group_by=[table2.c.othername],
                order_by=[table2.c.othername],
            ),
            "SELECT myothertable.othername, "
            "count(myothertable.otherid) AS count_1 "
            "FROM myothertable "
            "GROUP BY myothertable.othername ORDER BY myothertable.othername",
        )

    def test_custom_order_by_clause(self):
        class CustomCompiler(PGCompiler):
            def order_by_clause(self, select, **kw):
                return (
                    super(CustomCompiler, self).order_by_clause(select, **kw)
                    + " CUSTOMIZED"
                )

        class CustomDialect(PGDialect):
            name = "custom"
            statement_compiler = CustomCompiler

        stmt = select([table1.c.myid]).order_by(table1.c.myid)
        self.assert_compile(
            stmt,
            "SELECT mytable.myid FROM mytable ORDER BY "
            "mytable.myid CUSTOMIZED",
            dialect=CustomDialect(),
        )

    def test_custom_group_by_clause(self):
        class CustomCompiler(PGCompiler):
            def group_by_clause(self, select, **kw):
                return (
                    super(CustomCompiler, self).group_by_clause(select, **kw)
                    + " CUSTOMIZED"
                )

        class CustomDialect(PGDialect):
            name = "custom"
            statement_compiler = CustomCompiler

        stmt = select([table1.c.myid]).group_by(table1.c.myid)
        self.assert_compile(
            stmt,
            "SELECT mytable.myid FROM mytable GROUP BY "
            "mytable.myid CUSTOMIZED",
            dialect=CustomDialect(),
        )

    def test_for_update(self):
        self.assert_compile(
            table1.select(table1.c.myid == 7).with_for_update(),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE",
        )

        # not supported by dialect, should just use update
        self.assert_compile(
            table1.select(table1.c.myid == 7).with_for_update(nowait=True),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1 FOR UPDATE",
        )

    def test_alias(self):
        # test the alias for a table1.  column names stay the same,
        # table name "changes" to "foo".
        self.assert_compile(
            select([table1.alias("foo")]),
            "SELECT foo.myid, foo.name, foo.description FROM mytable AS foo",
        )

        for dialect in (oracle.dialect(),):
            self.assert_compile(
                select([table1.alias("foo")]),
                "SELECT foo.myid, foo.name, foo.description FROM mytable foo",
                dialect=dialect,
            )

        self.assert_compile(
            select([table1.alias()]),
            "SELECT mytable_1.myid, mytable_1.name, mytable_1.description "
            "FROM mytable AS mytable_1",
        )

        # create a select for a join of two tables.  use_labels
        # means the column names will have labels tablename_columnname,
        # which become the column keys accessible off the Selectable object.
        # also, only use one column from the second table and all columns
        # from the first table1.
        q = select(
            [table1, table2.c.otherid],
            table1.c.myid == table2.c.otherid,
            use_labels=True,
        )

        # make an alias of the "selectable".  column names
        # stay the same (i.e. the labels), table name "changes" to "t2view".
        a = q.alias("t2view")

        # select from that alias, also using labels.  two levels of labels
        # should produce two underscores.
        # also, reference the column "mytable_myid" off of the t2view alias.
        self.assert_compile(
            a.select(a.c.mytable_myid == 9, use_labels=True),
            "SELECT t2view.mytable_myid AS t2view_mytable_myid, "
            "t2view.mytable_name "
            "AS t2view_mytable_name, "
            "t2view.mytable_description AS t2view_mytable_description, "
            "t2view.myothertable_otherid AS t2view_myothertable_otherid FROM "
            "(SELECT mytable.myid AS mytable_myid, "
            "mytable.name AS mytable_name, "
            "mytable.description AS mytable_description, "
            "myothertable.otherid AS "
            "myothertable_otherid FROM mytable, myothertable "
            "WHERE mytable.myid = "
            "myothertable.otherid) AS t2view "
            "WHERE t2view.mytable_myid = :mytable_myid_1",
        )

    def test_alias_nesting_table(self):
        self.assert_compile(
            select([table1.alias("foo").alias("bar").alias("bat")]),
            "SELECT bat.myid, bat.name, bat.description FROM mytable AS bat",
        )

        self.assert_compile(
            select([table1.alias(None).alias("bar").alias("bat")]),
            "SELECT bat.myid, bat.name, bat.description FROM mytable AS bat",
        )

        self.assert_compile(
            select([table1.alias("foo").alias(None).alias("bat")]),
            "SELECT bat.myid, bat.name, bat.description FROM mytable AS bat",
        )

        self.assert_compile(
            select([table1.alias("foo").alias("bar").alias(None)]),
            "SELECT bar_1.myid, bar_1.name, bar_1.description "
            "FROM mytable AS bar_1",
        )

        self.assert_compile(
            select([table1.alias("foo").alias(None).alias(None)]),
            "SELECT anon_1.myid, anon_1.name, anon_1.description "
            "FROM mytable AS anon_1",
        )

    def test_alias_nesting_subquery(self):
        stmt = select([table1]).subquery()
        self.assert_compile(
            select([stmt.alias("foo").alias("bar").alias("bat")]),
            "SELECT bat.myid, bat.name, bat.description FROM "
            "(SELECT mytable.myid AS myid, mytable.name AS name, "
            "mytable.description AS description FROM mytable) AS bat",
        )

        self.assert_compile(
            select([stmt.alias("foo").alias(None).alias(None)]),
            "SELECT anon_1.myid, anon_1.name, anon_1.description FROM "
            "(SELECT mytable.myid AS myid, mytable.name AS name, "
            "mytable.description AS description FROM mytable) AS anon_1",
        )

    def test_prefix(self):
        self.assert_compile(
            table1.select()
            .prefix_with("SQL_CALC_FOUND_ROWS")
            .prefix_with("SQL_SOME_WEIRD_MYSQL_THING"),
            "SELECT SQL_CALC_FOUND_ROWS SQL_SOME_WEIRD_MYSQL_THING "
            "mytable.myid, mytable.name, mytable.description FROM mytable",
        )

    def test_prefix_dialect_specific(self):
        self.assert_compile(
            table1.select()
            .prefix_with("SQL_CALC_FOUND_ROWS", dialect="sqlite")
            .prefix_with("SQL_SOME_WEIRD_MYSQL_THING", dialect="mysql"),
            "SELECT SQL_SOME_WEIRD_MYSQL_THING "
            "mytable.myid, mytable.name, mytable.description FROM mytable",
            dialect=mysql.dialect(),
        )

    def test_collate(self):
        # columns clause
        self.assert_compile(
            select([column("x").collate("bar")]),
            "SELECT x COLLATE bar AS anon_1",
        )

        # WHERE clause
        self.assert_compile(
            select([column("x")]).where(column("x").collate("bar") == "foo"),
            "SELECT x WHERE (x COLLATE bar) = :param_1",
        )

        # ORDER BY clause
        self.assert_compile(
            select([column("x")]).order_by(column("x").collate("bar")),
            "SELECT x ORDER BY x COLLATE bar",
        )

    def test_literal(self):

        self.assert_compile(
            select([literal("foo")]), "SELECT :param_1 AS anon_1"
        )

        self.assert_compile(
            select([literal("foo") + literal("bar")], from_obj=[table1]),
            "SELECT :param_1 || :param_2 AS anon_1 FROM mytable",
        )

    def test_calculated_columns(self):
        value_tbl = table(
            "values",
            column("id", Integer),
            column("val1", Float),
            column("val2", Float),
        )

        self.assert_compile(
            select(
                [
                    value_tbl.c.id,
                    (value_tbl.c.val2 - value_tbl.c.val1) / value_tbl.c.val1,
                ]
            ),
            "SELECT values.id, (values.val2 - values.val1) "
            "/ values.val1 AS anon_1 FROM values",
        )

        self.assert_compile(
            select(
                [value_tbl.c.id],
                (value_tbl.c.val2 - value_tbl.c.val1) / value_tbl.c.val1 > 2.0,
            ),
            "SELECT values.id FROM values WHERE "
            "(values.val2 - values.val1) / values.val1 > :param_1",
        )

        self.assert_compile(
            select(
                [value_tbl.c.id],
                value_tbl.c.val1
                / (value_tbl.c.val2 - value_tbl.c.val1)
                / value_tbl.c.val1
                > 2.0,
            ),
            "SELECT values.id FROM values WHERE "
            "(values.val1 / (values.val2 - values.val1)) "
            "/ values.val1 > :param_1",
        )

    def test_percent_chars(self):
        t = table(
            "table%name",
            column("percent%"),
            column("%(oneofthese)s"),
            column("spaces % more spaces"),
        )
        self.assert_compile(
            t.select(use_labels=True),
            """SELECT "table%name"."percent%" AS "table%name_percent%", """
            """"table%name"."%(oneofthese)s" AS """
            """"table%name_%(oneofthese)s", """
            """"table%name"."spaces % more spaces" AS """
            """"table%name_spaces % """
            '''more spaces" FROM "table%name"''',
        )

    def test_joins(self):
        self.assert_compile(
            join(table2, table1, table1.c.myid == table2.c.otherid).select(),
            "SELECT myothertable.otherid, myothertable.othername, "
            "mytable.myid, mytable.name, mytable.description FROM "
            "myothertable JOIN mytable ON mytable.myid = myothertable.otherid",
        )

        self.assert_compile(
            select(
                [table1],
                from_obj=[
                    join(table1, table2, table1.c.myid == table2.c.otherid)
                ],
            ),
            "SELECT mytable.myid, mytable.name, mytable.description FROM "
            "mytable JOIN myothertable ON mytable.myid = myothertable.otherid",
        )

        self.assert_compile(
            select(
                [
                    join(
                        join(
                            table1, table2, table1.c.myid == table2.c.otherid
                        ),
                        table3,
                        table1.c.myid == table3.c.userid,
                    )
                ]
            ),
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "myothertable.otherid, myothertable.othername, "
            "thirdtable.userid, "
            "thirdtable.otherstuff FROM mytable JOIN myothertable "
            "ON mytable.myid ="
            " myothertable.otherid JOIN thirdtable ON "
            "mytable.myid = thirdtable.userid",
        )

        self.assert_compile(
            join(
                users, addresses, users.c.user_id == addresses.c.user_id
            ).select(),
            "SELECT users.user_id, users.user_name, users.password, "
            "addresses.address_id, addresses.user_id, addresses.street, "
            "addresses.city, addresses.state, addresses.zip "
            "FROM users JOIN addresses "
            "ON users.user_id = addresses.user_id",
        )

        self.assert_compile(
            select(
                [table1, table2, table3],
                from_obj=[
                    join(
                        table1, table2, table1.c.myid == table2.c.otherid
                    ).outerjoin(table3, table1.c.myid == table3.c.userid)
                ],
            ),
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "myothertable.otherid, myothertable.othername, "
            "thirdtable.userid,"
            " thirdtable.otherstuff FROM mytable "
            "JOIN myothertable ON mytable.myid "
            "= myothertable.otherid LEFT OUTER JOIN thirdtable "
            "ON mytable.myid ="
            " thirdtable.userid",
        )
        self.assert_compile(
            select(
                [table1, table2, table3],
                from_obj=[
                    outerjoin(
                        table1,
                        join(
                            table2, table3, table2.c.otherid == table3.c.userid
                        ),
                        table1.c.myid == table2.c.otherid,
                    )
                ],
            ),
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "myothertable.otherid, myothertable.othername, "
            "thirdtable.userid,"
            " thirdtable.otherstuff FROM mytable LEFT OUTER JOIN "
            "(myothertable "
            "JOIN thirdtable ON myothertable.otherid = "
            "thirdtable.userid) ON "
            "mytable.myid = myothertable.otherid",
        )

        query = select(
            [table1, table2],
            or_(
                table1.c.name == "fred",
                table1.c.myid == 10,
                table2.c.othername != "jack",
                text("EXISTS (select yay from foo where boo = lar)"),
            ),
            from_obj=[
                outerjoin(table1, table2, table1.c.myid == table2.c.otherid)
            ],
        )
        self.assert_compile(
            query,
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "myothertable.otherid, myothertable.othername "
            "FROM mytable LEFT OUTER JOIN myothertable ON mytable.myid = "
            "myothertable.otherid WHERE mytable.name = :name_1 OR "
            "mytable.myid = :myid_1 OR myothertable.othername != :othername_1 "
            "OR EXISTS (select yay from foo where boo = lar)",
        )

    def test_full_outer_join(self):
        for spec in [
            join(table1, table2, table1.c.myid == table2.c.otherid, full=True),
            outerjoin(
                table1, table2, table1.c.myid == table2.c.otherid, full=True
            ),
            table1.join(table2, table1.c.myid == table2.c.otherid, full=True),
            table1.outerjoin(
                table2, table1.c.myid == table2.c.otherid, full=True
            ),
        ]:
            stmt = select([table1]).select_from(spec)
        self.assert_compile(
            stmt,
            "SELECT mytable.myid, mytable.name, mytable.description FROM "
            "mytable FULL OUTER JOIN myothertable "
            "ON mytable.myid = myothertable.otherid",
        )

    def test_compound_selects(self):
        assert_raises_message(
            exc.ArgumentError,
            "All selectables passed to CompoundSelect "
            "must have identical numbers of columns; "
            "select #1 has 2 columns, select #2 has 3",
            union,
            table3.select(),
            table1.select(),
        )

        x = union(
            select([table1], table1.c.myid == 5),
            select([table1], table1.c.myid == 12),
            order_by=[table1.c.myid],
        )

        self.assert_compile(
            x,
            "SELECT mytable.myid, mytable.name, "
            "mytable.description "
            "FROM mytable WHERE "
            "mytable.myid = :myid_1 UNION "
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_2 "
            "ORDER BY myid",
        )

        x = union(select([table1]), select([table1]))
        x = union(x, select([table1]))
        self.assert_compile(
            x,
            "(SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable UNION SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable) UNION SELECT mytable.myid,"
            " mytable.name, mytable.description FROM mytable",
        )

        u1 = union(
            select([table1.c.myid, table1.c.name]),
            select([table2]),
            select([table3]),
        ).order_by("name")
        self.assert_compile(
            u1,
            "SELECT mytable.myid, mytable.name "
            "FROM mytable UNION SELECT myothertable.otherid, "
            "myothertable.othername FROM myothertable "
            "UNION SELECT thirdtable.userid, thirdtable.otherstuff "
            "FROM thirdtable ORDER BY name",
        )

        u1s = u1.subquery()
        assert u1s.corresponding_column(table2.c.otherid) is u1s.c.myid

        self.assert_compile(
            union(
                select([table1.c.myid, table1.c.name]),
                select([table2]),
                order_by=["myid"],
                offset=10,
                limit=5,
            ),
            # note table name is omitted here.  The CompoundSelect, inside of
            # _label_resolve_dict(),  creates a subquery of itself and then
            # turns "named_with_column" off,  so that we can order by the
            # "myid" name as relative to the CompoundSelect itself without it
            # having a name.
            "SELECT mytable.myid, mytable.name "
            "FROM mytable UNION SELECT myothertable.otherid, "
            "myothertable.othername "
            "FROM myothertable ORDER BY myid "
            "LIMIT :param_1 OFFSET :param_2",
            {"param_1": 5, "param_2": 10},
        )

        # these tests are mostly in test_text, however adding one here
        # to check the special thing CompoundSelect does with labels
        assert_raises_message(
            exc.CompileError,
            "Can't resolve label reference for ORDER BY / GROUP BY. Textual "
            "SQL expression 'noname'",
            union(
                select([table1.c.myid, table1.c.name]),
                select([table2]),
                order_by=["noname"],
            ).compile,
        )

        self.assert_compile(
            union(
                select(
                    [
                        table1.c.myid,
                        table1.c.name,
                        func.max(table1.c.description),
                    ],
                    table1.c.name == "name2",
                    group_by=[table1.c.myid, table1.c.name],
                ),
                table1.select(table1.c.name == "name1"),
            ),
            "SELECT mytable.myid, mytable.name, "
            "max(mytable.description) AS max_1 "
            "FROM mytable WHERE mytable.name = :name_1 "
            "GROUP BY mytable.myid, "
            "mytable.name UNION SELECT mytable.myid, mytable.name, "
            "mytable.description "
            "FROM mytable WHERE mytable.name = :name_2",
        )

        self.assert_compile(
            union(
                select([literal(100).label("value")]),
                select([literal(200).label("value")]),
            ),
            "SELECT :param_1 AS value UNION SELECT :param_2 AS value",
        )

        self.assert_compile(
            union_all(
                select([table1.c.myid]),
                union(select([table2.c.otherid]), select([table3.c.userid])),
            ),
            "SELECT mytable.myid FROM mytable UNION ALL "
            "(SELECT myothertable.otherid FROM myothertable UNION "
            "SELECT thirdtable.userid FROM thirdtable)",
        )

        s = select([column("foo"), column("bar")])

        self.assert_compile(
            union(s.order_by("foo"), s.order_by("bar")),
            "(SELECT foo, bar ORDER BY foo) UNION "
            "(SELECT foo, bar ORDER BY bar)",
        )
        self.assert_compile(
            union(
                s.order_by("foo").self_group(),
                s.order_by("bar").limit(10).self_group(),
            ),
            "(SELECT foo, bar ORDER BY foo) UNION (SELECT foo, "
            "bar ORDER BY bar LIMIT :param_1)",
            {"param_1": 10},
        )

    def test_dupe_cols_hey_we_can_union(self):
        """test the original inspiration for [ticket:4753]."""

        s1 = select([table1, table1.c.myid]).where(table1.c.myid == 5)
        s2 = select([table1, table2.c.otherid]).where(
            table1.c.myid == table2.c.otherid
        )
        self.assert_compile(
            union(s1, s2).order_by(s1.selected_columns.myid),
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "mytable.myid FROM mytable WHERE mytable.myid = :myid_1 "
            "UNION SELECT mytable.myid, mytable.name, mytable.description, "
            "myothertable.otherid FROM mytable, myothertable "
            "WHERE mytable.myid = myothertable.otherid ORDER BY myid",
        )

    def test_compound_grouping(self):
        s = select([column("foo"), column("bar")]).select_from(text("bat"))

        self.assert_compile(
            union(union(union(s, s), s), s),
            "((SELECT foo, bar FROM bat UNION SELECT foo, bar FROM bat) "
            "UNION SELECT foo, bar FROM bat) UNION SELECT foo, bar FROM bat",
        )

        self.assert_compile(
            union(s, s, s, s),
            "SELECT foo, bar FROM bat UNION SELECT foo, bar "
            "FROM bat UNION SELECT foo, bar FROM bat "
            "UNION SELECT foo, bar FROM bat",
        )

        self.assert_compile(
            union(s, union(s, union(s, s))),
            "SELECT foo, bar FROM bat UNION (SELECT foo, bar FROM bat "
            "UNION (SELECT foo, bar FROM bat "
            "UNION SELECT foo, bar FROM bat))",
        )

        self.assert_compile(
            select([s.alias()]),
            "SELECT anon_1.foo, anon_1.bar FROM "
            "(SELECT foo, bar FROM bat) AS anon_1",
        )

        self.assert_compile(
            select([union(s, s).alias()]),
            "SELECT anon_1.foo, anon_1.bar FROM "
            "(SELECT foo, bar FROM bat UNION "
            "SELECT foo, bar FROM bat) AS anon_1",
        )

        self.assert_compile(
            select([except_(s, s).alias()]),
            "SELECT anon_1.foo, anon_1.bar FROM "
            "(SELECT foo, bar FROM bat EXCEPT "
            "SELECT foo, bar FROM bat) AS anon_1",
        )

        # this query sqlite specifically chokes on
        self.assert_compile(
            union(except_(s, s), s),
            "(SELECT foo, bar FROM bat EXCEPT SELECT foo, bar FROM bat) "
            "UNION SELECT foo, bar FROM bat",
        )

        self.assert_compile(
            union(s, except_(s, s)),
            "SELECT foo, bar FROM bat "
            "UNION (SELECT foo, bar FROM bat EXCEPT SELECT foo, bar FROM bat)",
        )

        # this solves it
        self.assert_compile(
            union(except_(s, s).alias().select(), s),
            "SELECT anon_1.foo, anon_1.bar FROM "
            "(SELECT foo, bar FROM bat EXCEPT "
            "SELECT foo, bar FROM bat) AS anon_1 "
            "UNION SELECT foo, bar FROM bat",
        )

        self.assert_compile(
            except_(union(s, s), union(s, s)),
            "(SELECT foo, bar FROM bat UNION SELECT foo, bar FROM bat) "
            "EXCEPT (SELECT foo, bar FROM bat UNION SELECT foo, bar FROM bat)",
        )
        s2 = union(s, s)
        s3 = union(s2, s2)
        self.assert_compile(
            s3,
            "(SELECT foo, bar FROM bat "
            "UNION SELECT foo, bar FROM bat) "
            "UNION (SELECT foo, bar FROM bat "
            "UNION SELECT foo, bar FROM bat)",
        )

        self.assert_compile(
            union(intersect(s, s), intersect(s, s)),
            "(SELECT foo, bar FROM bat INTERSECT SELECT foo, bar FROM bat) "
            "UNION (SELECT foo, bar FROM bat INTERSECT "
            "SELECT foo, bar FROM bat)",
        )

        # tests for [ticket:2528]
        # sqlite hates all of these.
        self.assert_compile(
            union(s.limit(1), s.offset(2)),
            "(SELECT foo, bar FROM bat LIMIT :param_1) "
            "UNION (SELECT foo, bar FROM bat LIMIT -1 OFFSET :param_2)",
        )

        self.assert_compile(
            union(s.order_by(column("bar")), s.offset(2)),
            "(SELECT foo, bar FROM bat ORDER BY bar) "
            "UNION (SELECT foo, bar FROM bat LIMIT -1 OFFSET :param_1)",
        )

        self.assert_compile(
            union(
                s.limit(1).alias("a").element, s.limit(2).alias("b").element
            ),
            "(SELECT foo, bar FROM bat LIMIT :param_1) "
            "UNION (SELECT foo, bar FROM bat LIMIT :param_2)",
        )

        self.assert_compile(
            union(s.limit(1).self_group(), s.limit(2).self_group()),
            "(SELECT foo, bar FROM bat LIMIT :param_1) "
            "UNION (SELECT foo, bar FROM bat LIMIT :param_2)",
        )

        self.assert_compile(
            union(s.limit(1), s.limit(2).offset(3)).alias().select(),
            "SELECT anon_1.foo, anon_1.bar FROM "
            "((SELECT foo, bar FROM bat LIMIT :param_1) "
            "UNION (SELECT foo, bar FROM bat LIMIT :param_2 OFFSET :param_3)) "
            "AS anon_1",
        )

        # this version works for SQLite
        self.assert_compile(
            union(s.limit(1).alias().select(), s.offset(2).alias().select()),
            "SELECT anon_1.foo, anon_1.bar "
            "FROM (SELECT foo, bar FROM bat"
            " LIMIT :param_1) AS anon_1 "
            "UNION SELECT anon_2.foo, anon_2.bar "
            "FROM (SELECT foo, bar "
            "FROM bat"
            " LIMIT -1 OFFSET :param_2) AS anon_2",
        )

    def test_cast(self):
        tbl = table(
            "casttest",
            column("id", Integer),
            column("v1", Float),
            column("v2", Float),
            column("ts", TIMESTAMP),
        )

        def check_results(dialect, expected_results, literal):
            eq_(
                len(expected_results),
                5,
                "Incorrect number of expected results",
            )
            eq_(
                str(cast(tbl.c.v1, Numeric).compile(dialect=dialect)),
                "CAST(casttest.v1 AS %s)" % expected_results[0],
            )
            eq_(
                str(tbl.c.v1.cast(Numeric).compile(dialect=dialect)),
                "CAST(casttest.v1 AS %s)" % expected_results[0],
            )
            eq_(
                str(cast(tbl.c.v1, Numeric(12, 9)).compile(dialect=dialect)),
                "CAST(casttest.v1 AS %s)" % expected_results[1],
            )
            eq_(
                str(cast(tbl.c.ts, Date).compile(dialect=dialect)),
                "CAST(casttest.ts AS %s)" % expected_results[2],
            )
            eq_(
                str(cast(1234, Text).compile(dialect=dialect)),
                "CAST(%s AS %s)" % (literal, expected_results[3]),
            )
            eq_(
                str(cast("test", String(20)).compile(dialect=dialect)),
                "CAST(%s AS %s)" % (literal, expected_results[4]),
            )

            # fixme: shoving all of this dialect-specific stuff in one test
            # is now officially completely ridiculous AND non-obviously omits
            # coverage on other dialects.
            sel = select([tbl, cast(tbl.c.v1, Numeric)]).compile(
                dialect=dialect
            )
            if isinstance(dialect, type(mysql.dialect())):
                eq_(
                    str(sel),
                    "SELECT casttest.id, casttest.v1, casttest.v2, "
                    "casttest.ts, "
                    "CAST(casttest.v1 AS DECIMAL) AS v1 \nFROM casttest",
                )
            else:
                eq_(
                    str(sel),
                    "SELECT casttest.id, casttest.v1, casttest.v2, "
                    "casttest.ts, CAST(casttest.v1 AS NUMERIC) AS "
                    "v1 \nFROM casttest",
                )

        # first test with PostgreSQL engine
        check_results(
            postgresql.dialect(),
            ["NUMERIC", "NUMERIC(12, 9)", "DATE", "TEXT", "VARCHAR(20)"],
            "%(param_1)s",
        )

        # then the Oracle engine
        check_results(
            oracle.dialect(),
            ["NUMERIC", "NUMERIC(12, 9)", "DATE", "CLOB", "VARCHAR2(20 CHAR)"],
            ":param_1",
        )

        # then the sqlite engine
        check_results(
            sqlite.dialect(),
            ["NUMERIC", "NUMERIC(12, 9)", "DATE", "TEXT", "VARCHAR(20)"],
            "?",
        )

        # then the MySQL engine
        check_results(
            mysql.dialect(),
            ["DECIMAL", "DECIMAL(12, 9)", "DATE", "CHAR", "CHAR(20)"],
            "%s",
        )

        self.assert_compile(
            cast(text("NULL"), Integer),
            "CAST(NULL AS INTEGER)",
            dialect=sqlite.dialect(),
        )
        self.assert_compile(
            cast(null(), Integer),
            "CAST(NULL AS INTEGER)",
            dialect=sqlite.dialect(),
        )
        self.assert_compile(
            cast(literal_column("NULL"), Integer),
            "CAST(NULL AS INTEGER)",
            dialect=sqlite.dialect(),
        )

    def test_over(self):
        self.assert_compile(func.row_number().over(), "row_number() OVER ()")
        self.assert_compile(
            func.row_number().over(
                order_by=[table1.c.name, table1.c.description]
            ),
            "row_number() OVER (ORDER BY mytable.name, mytable.description)",
        )
        self.assert_compile(
            func.row_number().over(
                partition_by=[table1.c.name, table1.c.description]
            ),
            "row_number() OVER (PARTITION BY mytable.name, "
            "mytable.description)",
        )
        self.assert_compile(
            func.row_number().over(
                partition_by=[table1.c.name], order_by=[table1.c.description]
            ),
            "row_number() OVER (PARTITION BY mytable.name "
            "ORDER BY mytable.description)",
        )
        self.assert_compile(
            func.row_number().over(
                partition_by=table1.c.name, order_by=table1.c.description
            ),
            "row_number() OVER (PARTITION BY mytable.name "
            "ORDER BY mytable.description)",
        )

        self.assert_compile(
            func.row_number().over(
                partition_by=table1.c.name,
                order_by=[table1.c.name, table1.c.description],
            ),
            "row_number() OVER (PARTITION BY mytable.name "
            "ORDER BY mytable.name, mytable.description)",
        )

        self.assert_compile(
            func.row_number().over(
                partition_by=[], order_by=[table1.c.name, table1.c.description]
            ),
            "row_number() OVER (ORDER BY mytable.name, mytable.description)",
        )

        self.assert_compile(
            func.row_number().over(
                partition_by=[table1.c.name, table1.c.description], order_by=[]
            ),
            "row_number() OVER (PARTITION BY mytable.name, "
            "mytable.description)",
        )

        self.assert_compile(
            func.row_number().over(partition_by=[], order_by=[]),
            "row_number() OVER ()",
        )
        self.assert_compile(
            select(
                [
                    func.row_number()
                    .over(order_by=table1.c.description)
                    .label("foo")
                ]
            ),
            "SELECT row_number() OVER (ORDER BY mytable.description) "
            "AS foo FROM mytable",
        )

        # test from_obj generation.
        # from func:
        self.assert_compile(
            select(
                [func.max(table1.c.name).over(partition_by=["description"])]
            ),
            "SELECT max(mytable.name) OVER (PARTITION BY mytable.description) "
            "AS anon_1 FROM mytable",
        )
        # from partition_by
        self.assert_compile(
            select([func.row_number().over(partition_by=[table1.c.name])]),
            "SELECT row_number() OVER (PARTITION BY mytable.name) "
            "AS anon_1 FROM mytable",
        )
        # from order_by
        self.assert_compile(
            select([func.row_number().over(order_by=table1.c.name)]),
            "SELECT row_number() OVER (ORDER BY mytable.name) "
            "AS anon_1 FROM mytable",
        )

        # this tests that _from_objects
        # concantenates OK
        self.assert_compile(
            select([column("x") + over(func.foo())]),
            "SELECT x + foo() OVER () AS anon_1",
        )

        # test a reference to a label that in the referecned selectable;
        # this resolves
        expr = (table1.c.myid + 5).label("sum")
        stmt = select([expr]).alias()
        self.assert_compile(
            select([stmt.c.sum, func.row_number().over(order_by=stmt.c.sum)]),
            "SELECT anon_1.sum, row_number() OVER (ORDER BY anon_1.sum) "
            "AS anon_2 FROM (SELECT mytable.myid + :myid_1 AS sum "
            "FROM mytable) AS anon_1",
        )

        # test a reference to a label that's at the same level as the OVER
        # in the columns clause; doesn't resolve
        expr = (table1.c.myid + 5).label("sum")
        self.assert_compile(
            select([expr, func.row_number().over(order_by=expr)]),
            "SELECT mytable.myid + :myid_1 AS sum, "
            "row_number() OVER "
            "(ORDER BY mytable.myid + :myid_1) AS anon_1 FROM mytable",
        )

    def test_over_framespec(self):

        expr = table1.c.myid
        self.assert_compile(
            select([func.row_number().over(order_by=expr, rows=(0, None))]),
            "SELECT row_number() OVER "
            "(ORDER BY mytable.myid ROWS BETWEEN CURRENT "
            "ROW AND UNBOUNDED FOLLOWING)"
            " AS anon_1 FROM mytable",
        )

        self.assert_compile(
            select([func.row_number().over(order_by=expr, rows=(None, None))]),
            "SELECT row_number() OVER "
            "(ORDER BY mytable.myid ROWS BETWEEN UNBOUNDED "
            "PRECEDING AND UNBOUNDED FOLLOWING)"
            " AS anon_1 FROM mytable",
        )

        self.assert_compile(
            select([func.row_number().over(order_by=expr, range_=(None, 0))]),
            "SELECT row_number() OVER "
            "(ORDER BY mytable.myid RANGE BETWEEN "
            "UNBOUNDED PRECEDING AND CURRENT ROW)"
            " AS anon_1 FROM mytable",
        )

        self.assert_compile(
            select([func.row_number().over(order_by=expr, range_=(-5, 10))]),
            "SELECT row_number() OVER "
            "(ORDER BY mytable.myid RANGE BETWEEN "
            ":param_1 PRECEDING AND :param_2 FOLLOWING)"
            " AS anon_1 FROM mytable",
            checkparams={"param_1": 5, "param_2": 10},
        )

        self.assert_compile(
            select([func.row_number().over(order_by=expr, range_=(1, 10))]),
            "SELECT row_number() OVER "
            "(ORDER BY mytable.myid RANGE BETWEEN "
            ":param_1 FOLLOWING AND :param_2 FOLLOWING)"
            " AS anon_1 FROM mytable",
            checkparams={"param_1": 1, "param_2": 10},
        )

        self.assert_compile(
            select([func.row_number().over(order_by=expr, range_=(-10, -1))]),
            "SELECT row_number() OVER "
            "(ORDER BY mytable.myid RANGE BETWEEN "
            ":param_1 PRECEDING AND :param_2 PRECEDING)"
            " AS anon_1 FROM mytable",
            checkparams={"param_1": 10, "param_2": 1},
        )

    def test_over_invalid_framespecs(self):
        assert_raises_message(
            exc.ArgumentError,
            "Integer or None expected for range value",
            func.row_number().over,
            range_=("foo", 8),
        )

        assert_raises_message(
            exc.ArgumentError,
            "Integer or None expected for range value",
            func.row_number().over,
            range_=(-5, "foo"),
        )

        assert_raises_message(
            exc.ArgumentError,
            "'range_' and 'rows' are mutually exclusive",
            func.row_number().over,
            range_=(-5, 8),
            rows=(-2, 5),
        )

    def test_over_within_group(self):
        from sqlalchemy import within_group

        stmt = select(
            [
                table1.c.myid,
                within_group(
                    func.percentile_cont(0.5), table1.c.name.desc()
                ).over(
                    range_=(1, 2),
                    partition_by=table1.c.name,
                    order_by=table1.c.myid,
                ),
            ]
        )
        eq_ignore_whitespace(
            str(stmt),
            "SELECT mytable.myid, percentile_cont(:percentile_cont_1) "
            "WITHIN GROUP (ORDER BY mytable.name DESC) "
            "OVER (PARTITION BY mytable.name ORDER BY mytable.myid "
            "RANGE BETWEEN :param_1 FOLLOWING AND :param_2 FOLLOWING) "
            "AS anon_1 FROM mytable",
        )

        stmt = select(
            [
                table1.c.myid,
                within_group(
                    func.percentile_cont(0.5), table1.c.name.desc()
                ).over(
                    rows=(1, 2),
                    partition_by=table1.c.name,
                    order_by=table1.c.myid,
                ),
            ]
        )
        eq_ignore_whitespace(
            str(stmt),
            "SELECT mytable.myid, percentile_cont(:percentile_cont_1) "
            "WITHIN GROUP (ORDER BY mytable.name DESC) "
            "OVER (PARTITION BY mytable.name ORDER BY mytable.myid "
            "ROWS BETWEEN :param_1 FOLLOWING AND :param_2 FOLLOWING) "
            "AS anon_1 FROM mytable",
        )

    def test_date_between(self):
        import datetime

        table = Table("dt", metadata, Column("date", Date))
        self.assert_compile(
            table.select(
                table.c.date.between(
                    datetime.date(2006, 6, 1), datetime.date(2006, 6, 5)
                )
            ),
            "SELECT dt.date FROM dt WHERE dt.date BETWEEN :date_1 AND :date_2",
            checkparams={
                "date_1": datetime.date(2006, 6, 1),
                "date_2": datetime.date(2006, 6, 5),
            },
        )

        self.assert_compile(
            table.select(
                sql.between(
                    table.c.date,
                    datetime.date(2006, 6, 1),
                    datetime.date(2006, 6, 5),
                )
            ),
            "SELECT dt.date FROM dt WHERE dt.date BETWEEN :date_1 AND :date_2",
            checkparams={
                "date_1": datetime.date(2006, 6, 1),
                "date_2": datetime.date(2006, 6, 5),
            },
        )

    def test_delayed_col_naming(self):
        my_str = Column(String)

        sel1 = select([my_str])

        assert_raises_message(
            exc.InvalidRequestError,
            "Cannot initialize a sub-selectable with this Column",
            lambda: sel1.subquery().c,
        )

        # calling label or scalar_subquery doesn't compile
        # anything.
        sel2 = select([func.substr(my_str, 2, 3)]).label("my_substr")

        assert_raises_message(
            exc.CompileError,
            "Cannot compile Column object until its 'name' is assigned.",
            sel2.compile,
            dialect=default.DefaultDialect(),
        )

        sel3 = select([my_str]).scalar_subquery()
        assert_raises_message(
            exc.CompileError,
            "Cannot compile Column object until its 'name' is assigned.",
            sel3.compile,
            dialect=default.DefaultDialect(),
        )

        my_str.name = "foo"

        self.assert_compile(sel1, "SELECT foo")
        self.assert_compile(
            sel2, "(SELECT substr(foo, :substr_2, :substr_3) AS substr_1)"
        )

        self.assert_compile(sel3, "(SELECT foo)")

    def test_naming(self):
        # TODO: the part where we check c.keys() are  not "compile" tests, they
        # belong probably in test_selectable, or some broken up
        # version of that suite

        f1 = func.hoho(table1.c.name)
        s1 = select(
            [
                table1.c.myid,
                table1.c.myid.label("foobar"),
                f1,
                func.lala(table1.c.name).label("gg"),
            ]
        )

        eq_(list(s1.subquery().c.keys()), ["myid", "foobar", str(f1), "gg"])

        meta = MetaData()
        t1 = Table("mytable", meta, Column("col1", Integer))

        exprs = (
            table1.c.myid == 12,
            func.hoho(table1.c.myid),
            cast(table1.c.name, Numeric),
            literal("x"),
        )
        for col, key, expr, lbl in (
            (table1.c.name, "name", "mytable.name", None),
            (exprs[0], str(exprs[0]), "mytable.myid = :myid_1", "anon_1"),
            (exprs[1], str(exprs[1]), "hoho(mytable.myid)", "hoho_1"),
            (
                exprs[2],
                str(exprs[2]),
                "CAST(mytable.name AS NUMERIC)",
                "name",  # due to [ticket:4449]
            ),
            (t1.c.col1, "col1", "mytable.col1", None),
            (
                column("some wacky thing"),
                "some wacky thing",
                '"some wacky thing"',
                "",
            ),
            (exprs[3], exprs[3].key, ":param_1", "anon_1"),
        ):
            if getattr(col, "table", None) is not None:
                t = col.table
            else:
                t = table1

            s1 = select([col], from_obj=t)
            assert list(s1.subquery().c.keys()) == [key], list(s1.c.keys())

            if lbl:
                self.assert_compile(
                    s1, "SELECT %s AS %s FROM mytable" % (expr, lbl)
                )
            else:
                self.assert_compile(s1, "SELECT %s FROM mytable" % (expr,))

            s1 = select([s1.subquery()])
            if lbl:
                alias_ = "anon_2" if lbl == "anon_1" else "anon_1"
                self.assert_compile(
                    s1,
                    "SELECT %s.%s FROM (SELECT %s AS %s FROM mytable) AS %s"
                    % (alias_, lbl, expr, lbl, alias_),
                )
            elif col.table is not None:
                # sqlite rule labels subquery columns
                self.assert_compile(
                    s1,
                    "SELECT anon_1.%s FROM (SELECT %s AS %s FROM mytable) "
                    "AS anon_1" % (key, expr, key),
                )
            else:
                self.assert_compile(
                    s1,
                    "SELECT anon_1.%s FROM (SELECT %s FROM mytable) AS anon_1"
                    % (expr, expr),
                )

    def test_hints(self):
        s = select([table1.c.myid]).with_hint(table1, "test hint %(name)s")

        s2 = (
            select([table1.c.myid])
            .with_hint(table1, "index(%(name)s idx)", "oracle")
            .with_hint(table1, "WITH HINT INDEX idx", "sybase")
        )

        a1 = table1.alias()
        s3 = select([a1.c.myid]).with_hint(a1, "index(%(name)s hint)")

        subs4 = (
            select([table1, table2])
            .select_from(
                table1.join(table2, table1.c.myid == table2.c.otherid)
            )
            .with_hint(table1, "hint1")
        ).subquery()

        s4 = (
            select([table3])
            .select_from(
                table3.join(subs4, subs4.c.othername == table3.c.otherstuff)
            )
            .with_hint(table3, "hint3")
        )

        t1 = table("QuotedName", column("col1"))
        s6 = (
            select([t1.c.col1])
            .where(t1.c.col1 > 10)
            .with_hint(t1, "%(name)s idx1")
        )
        a2 = t1.alias("SomeName")
        s7 = (
            select([a2.c.col1])
            .where(a2.c.col1 > 10)
            .with_hint(a2, "%(name)s idx1")
        )

        mysql_d, oracle_d, sybase_d = (
            mysql.dialect(),
            oracle.dialect(),
            sybase.dialect(),
        )

        for stmt, dialect, expected in [
            (s, mysql_d, "SELECT mytable.myid FROM mytable test hint mytable"),
            (
                s,
                oracle_d,
                "SELECT /*+ test hint mytable */ mytable.myid FROM mytable",
            ),
            (
                s,
                sybase_d,
                "SELECT mytable.myid FROM mytable test hint mytable",
            ),
            (s2, mysql_d, "SELECT mytable.myid FROM mytable"),
            (
                s2,
                oracle_d,
                "SELECT /*+ index(mytable idx) */ mytable.myid FROM mytable",
            ),
            (
                s2,
                sybase_d,
                "SELECT mytable.myid FROM mytable WITH HINT INDEX idx",
            ),
            (
                s3,
                mysql_d,
                "SELECT mytable_1.myid FROM mytable AS mytable_1 "
                "index(mytable_1 hint)",
            ),
            (
                s3,
                oracle_d,
                "SELECT /*+ index(mytable_1 hint) */ mytable_1.myid FROM "
                "mytable mytable_1",
            ),
            (
                s3,
                sybase_d,
                "SELECT mytable_1.myid FROM mytable AS mytable_1 "
                "index(mytable_1 hint)",
            ),
            (
                s4,
                mysql_d,
                "SELECT thirdtable.userid, thirdtable.otherstuff "
                "FROM thirdtable "
                "hint3 INNER JOIN (SELECT mytable.myid AS myid, "
                "mytable.name AS name, "
                "mytable.description AS description, "
                "myothertable.otherid AS otherid, "
                "myothertable.othername AS othername FROM mytable hint1 INNER "
                "JOIN myothertable ON "
                "mytable.myid = myothertable.otherid) AS anon_1 "
                "ON anon_1.othername = thirdtable.otherstuff",
            ),
            (
                s4,
                sybase_d,
                "SELECT thirdtable.userid, thirdtable.otherstuff "
                "FROM thirdtable "
                "hint3 JOIN (SELECT mytable.myid AS myid, "
                "mytable.name AS name, "
                "mytable.description AS description, "
                "myothertable.otherid AS otherid, "
                "myothertable.othername AS othername FROM mytable hint1 "
                "JOIN myothertable ON "
                "mytable.myid = myothertable.otherid) AS anon_1 "
                "ON anon_1.othername = thirdtable.otherstuff",
            ),
            (
                s4,
                oracle_d,
                "SELECT /*+ hint3 */ thirdtable.userid, thirdtable.otherstuff "
                "FROM thirdtable JOIN (SELECT /*+ hint1 */ "
                "mytable.myid AS myid,"
                " mytable.name AS name, mytable.description AS description, "
                "myothertable.otherid AS otherid,"
                " myothertable.othername AS othername "
                "FROM mytable JOIN myothertable ON "
                "mytable.myid = myothertable.otherid) anon_1 ON "
                "anon_1.othername = thirdtable.otherstuff",
            ),
            (
                s6,
                oracle_d,
                """SELECT /*+ "QuotedName" idx1 */ "QuotedName".col1 """
                """FROM "QuotedName" WHERE "QuotedName".col1 > :col1_1""",
            ),
            (
                s7,
                oracle_d,
                """SELECT /*+ "SomeName" idx1 */ "SomeName".col1 FROM """
                """"QuotedName" "SomeName" WHERE "SomeName".col1 > :col1_1""",
            ),
        ]:
            self.assert_compile(stmt, expected, dialect=dialect)

    def test_statement_hints(self):

        stmt = (
            select([table1.c.myid])
            .with_statement_hint("test hint one")
            .with_statement_hint("test hint two", "mysql")
        )

        self.assert_compile(
            stmt, "SELECT mytable.myid FROM mytable test hint one"
        )

        self.assert_compile(
            stmt,
            "SELECT mytable.myid FROM mytable test hint one test hint two",
            dialect="mysql",
        )

    def test_literal_as_text_fromstring(self):
        self.assert_compile(and_(text("a"), text("b")), "a AND b")

    def test_literal_as_text_nonstring_raise(self):
        assert_raises(exc.ArgumentError, and_, ("a",), ("b",))


class BindParameterTest(AssertsCompiledSQL, fixtures.TestBase):
    __dialect__ = "default"

    def test_binds(self):
        for (
            stmt,
            expected_named_stmt,
            expected_positional_stmt,
            expected_default_params_dict,
            expected_default_params_list,
            test_param_dict,
            expected_test_params_dict,
            expected_test_params_list,
        ) in [
            (
                select(
                    [table1, table2],
                    and_(
                        table1.c.myid == table2.c.otherid,
                        table1.c.name == bindparam("mytablename"),
                    ),
                ),
                "SELECT mytable.myid, mytable.name, mytable.description, "
                "myothertable.otherid, myothertable.othername FROM mytable, "
                "myothertable WHERE mytable.myid = myothertable.otherid "
                "AND mytable.name = :mytablename",
                "SELECT mytable.myid, mytable.name, mytable.description, "
                "myothertable.otherid, myothertable.othername FROM mytable, "
                "myothertable WHERE mytable.myid = myothertable.otherid AND "
                "mytable.name = ?",
                {"mytablename": None},
                [None],
                {"mytablename": 5},
                {"mytablename": 5},
                [5],
            ),
            (
                select(
                    [table1],
                    or_(
                        table1.c.myid == bindparam("myid"),
                        table2.c.otherid == bindparam("myid"),
                    ),
                ),
                "SELECT mytable.myid, mytable.name, mytable.description "
                "FROM mytable, myothertable WHERE mytable.myid = :myid "
                "OR myothertable.otherid = :myid",
                "SELECT mytable.myid, mytable.name, mytable.description "
                "FROM mytable, myothertable WHERE mytable.myid = ? "
                "OR myothertable.otherid = ?",
                {"myid": None},
                [None, None],
                {"myid": 5},
                {"myid": 5},
                [5, 5],
            ),
            (
                text(
                    "SELECT mytable.myid, mytable.name, "
                    "mytable.description FROM "
                    "mytable, myothertable WHERE mytable.myid = :myid OR "
                    "myothertable.otherid = :myid"
                ),
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = :myid OR "
                "myothertable.otherid = :myid",
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = ? OR "
                "myothertable.otherid = ?",
                {"myid": None},
                [None, None],
                {"myid": 5},
                {"myid": 5},
                [5, 5],
            ),
            (
                select(
                    [table1],
                    or_(
                        table1.c.myid == bindparam("myid", unique=True),
                        table2.c.otherid == bindparam("myid", unique=True),
                    ),
                ),
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = "
                ":myid_1 OR myothertable.otherid = :myid_2",
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = ? "
                "OR myothertable.otherid = ?",
                {"myid_1": None, "myid_2": None},
                [None, None],
                {"myid_1": 5, "myid_2": 6},
                {"myid_1": 5, "myid_2": 6},
                [5, 6],
            ),
            (
                bindparam("test", type_=String, required=False) + text("'hi'"),
                ":test || 'hi'",
                "? || 'hi'",
                {"test": None},
                [None],
                {},
                {"test": None},
                [None],
            ),
            (
                # testing select.params() here - bindparam() objects
                # must get required flag set to False
                select(
                    [table1],
                    or_(
                        table1.c.myid == bindparam("myid"),
                        table2.c.otherid == bindparam("myotherid"),
                    ),
                ).params({"myid": 8, "myotherid": 7}),
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = "
                ":myid OR myothertable.otherid = :myotherid",
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = "
                "? OR myothertable.otherid = ?",
                {"myid": 8, "myotherid": 7},
                [8, 7],
                {"myid": 5},
                {"myid": 5, "myotherid": 7},
                [5, 7],
            ),
            (
                select(
                    [table1],
                    or_(
                        table1.c.myid
                        == bindparam("myid", value=7, unique=True),
                        table2.c.otherid
                        == bindparam("myid", value=8, unique=True),
                    ),
                ),
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = "
                ":myid_1 OR myothertable.otherid = :myid_2",
                "SELECT mytable.myid, mytable.name, mytable.description FROM "
                "mytable, myothertable WHERE mytable.myid = "
                "? OR myothertable.otherid = ?",
                {"myid_1": 7, "myid_2": 8},
                [7, 8],
                {"myid_1": 5, "myid_2": 6},
                {"myid_1": 5, "myid_2": 6},
                [5, 6],
            ),
        ]:

            self.assert_compile(
                stmt, expected_named_stmt, params=expected_default_params_dict
            )
            self.assert_compile(
                stmt, expected_positional_stmt, dialect=sqlite.dialect()
            )
            nonpositional = stmt.compile()
            positional = stmt.compile(dialect=sqlite.dialect())
            pp = positional.params
            eq_(
                [pp[k] for k in positional.positiontup],
                expected_default_params_list,
            )

            eq_(
                nonpositional.construct_params(test_param_dict),
                expected_test_params_dict,
            )
            pp = positional.construct_params(test_param_dict)
            eq_(
                [pp[k] for k in positional.positiontup],
                expected_test_params_list,
            )

        # check that params() doesn't modify original statement
        s = select(
            [table1],
            or_(
                table1.c.myid == bindparam("myid"),
                table2.c.otherid == bindparam("myotherid"),
            ),
        )
        s2 = s.params({"myid": 8, "myotherid": 7})
        s3 = s2.params({"myid": 9})
        assert s.compile().params == {"myid": None, "myotherid": None}
        assert s2.compile().params == {"myid": 8, "myotherid": 7}
        assert s3.compile().params == {"myid": 9, "myotherid": 7}

        # test using same 'unique' param object twice in one compile
        s = (
            select([table1.c.myid])
            .where(table1.c.myid == 12)
            .scalar_subquery()
        )
        s2 = select([table1, s], table1.c.myid == s)
        self.assert_compile(
            s2,
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "(SELECT mytable.myid FROM mytable WHERE mytable.myid = "
            ":myid_1) AS anon_1 FROM mytable WHERE mytable.myid = "
            "(SELECT mytable.myid FROM mytable WHERE mytable.myid = :myid_1)",
        )
        positional = s2.compile(dialect=sqlite.dialect())

        pp = positional.params
        assert [pp[k] for k in positional.positiontup] == [12, 12]

        # check that conflicts with "unique" params are caught
        s = select(
            [table1],
            or_(table1.c.myid == 7, table1.c.myid == bindparam("myid_1")),
        )
        assert_raises_message(
            exc.CompileError,
            "conflicts with unique bind parameter " "of the same name",
            str,
            s,
        )

        s = select(
            [table1],
            or_(
                table1.c.myid == 7,
                table1.c.myid == 8,
                table1.c.myid == bindparam("myid_1"),
            ),
        )
        assert_raises_message(
            exc.CompileError,
            "conflicts with unique bind parameter " "of the same name",
            str,
            s,
        )

    def _test_binds_no_hash_collision(self):
        """test that construct_params doesn't corrupt dict
            due to hash collisions"""

        total_params = 100000

        in_clause = [":in%d" % i for i in range(total_params)]
        params = dict(("in%d" % i, i) for i in range(total_params))
        t = text("text clause %s" % ", ".join(in_clause))
        eq_(len(t.bindparams), total_params)
        c = t.compile()
        pp = c.construct_params(params)
        eq_(len(set(pp)), total_params, "%s %s" % (len(set(pp)), len(pp)))
        eq_(len(set(pp.values())), total_params)

    def test_bind_anon_name_no_special_chars(self):
        for paramstyle in "named", "pyformat":
            dialect = default.DefaultDialect()
            dialect.paramstyle = paramstyle

            for name, named, pyformat in [
                ("%(my name)s", ":my_name_s_1", "%(my_name_s_1)s"),
                ("myname(foo)", ":myname_foo_1", "%(myname_foo_1)s"),
                (
                    "this is a name",
                    ":this_is_a_name_1",
                    "%(this_is_a_name_1)s",
                ),
                ("_leading_one", ":leading_one_1", "%(leading_one_1)s"),
                ("3leading_two", ":3leading_two_1", "%(3leading_two_1)s"),
                ("$leading_three", ":leading_three_1", "%(leading_three_1)s"),
                ("%(tricky", ":tricky_1", "%(tricky_1)s"),
                ("5(tricky", ":5_tricky_1", "%(5_tricky_1)s"),
            ]:
                t = table("t", column(name, String))
                expr = t.c[name] == "foo"

                self.assert_compile(
                    expr,
                    "t.%s = %s"
                    % (
                        dialect.identifier_preparer.quote(name),
                        named if paramstyle == "named" else pyformat,
                    ),
                    dialect=dialect,
                    checkparams={named[1:]: "foo"},
                )

    def test_bind_anon_name_special_chars_uniqueify_one(self):
        # test that the chars are escaped before doing the counter,
        # otherwise these become the same name and bind params will conflict
        t = table("t", column("_3foo"), column("4%foo"))

        self.assert_compile(
            (t.c["_3foo"] == "foo") & (t.c["4%foo"] == "bar"),
            't._3foo = :3foo_1 AND t."4%foo" = :4_foo_1',
            checkparams={"3foo_1": "foo", "4_foo_1": "bar"},
        )

    def test_bind_anon_name_special_chars_uniqueify_two(self):

        t = table("t", column("_3foo"), column("4(foo"))

        self.assert_compile(
            (t.c["_3foo"] == "foo") & (t.c["4(foo"] == "bar"),
            't._3foo = :3foo_1 AND t."4(foo" = :4_foo_1',
            checkparams={"3foo_1": "foo", "4_foo_1": "bar"},
        )

    def test_bind_as_col(self):
        t = table("foo", column("id"))

        s = select([t, literal("lala").label("hoho")])
        self.assert_compile(s, "SELECT foo.id, :param_1 AS hoho FROM foo")

        assert [str(c) for c in s.subquery().c] == ["anon_1.id", "anon_1.hoho"]

    def test_bind_callable(self):
        expr = column("x") == bindparam("key", callable_=lambda: 12)
        self.assert_compile(expr, "x = :key", {"x": 12})

    def test_bind_params_missing(self):
        assert_raises_message(
            exc.InvalidRequestError,
            r"A value is required for bind parameter 'x'",
            select([table1])
            .where(
                and_(
                    table1.c.myid == bindparam("x", required=True),
                    table1.c.name == bindparam("y", required=True),
                )
            )
            .compile()
            .construct_params,
            params=dict(y=5),
        )

        assert_raises_message(
            exc.InvalidRequestError,
            r"A value is required for bind parameter 'x'",
            select([table1])
            .where(table1.c.myid == bindparam("x", required=True))
            .compile()
            .construct_params,
        )

        assert_raises_message(
            exc.InvalidRequestError,
            r"A value is required for bind parameter 'x', "
            "in parameter group 2",
            select([table1])
            .where(
                and_(
                    table1.c.myid == bindparam("x", required=True),
                    table1.c.name == bindparam("y", required=True),
                )
            )
            .compile()
            .construct_params,
            params=dict(y=5),
            _group_number=2,
        )

        assert_raises_message(
            exc.InvalidRequestError,
            r"A value is required for bind parameter 'x', "
            "in parameter group 2",
            select([table1])
            .where(table1.c.myid == bindparam("x", required=True))
            .compile()
            .construct_params,
            _group_number=2,
        )

    def test_tuple(self):
        self.assert_compile(
            tuple_(table1.c.myid, table1.c.name).in_([(1, "foo"), (5, "bar")]),
            "(mytable.myid, mytable.name) IN "
            "((:param_1, :param_2), (:param_3, :param_4))",
        )

        dialect = default.DefaultDialect()
        dialect.tuple_in_values = True
        self.assert_compile(
            tuple_(table1.c.myid, table1.c.name).in_([(1, "foo"), (5, "bar")]),
            "(mytable.myid, mytable.name) IN "
            "(VALUES (:param_1, :param_2), (:param_3, :param_4))",
            dialect=dialect,
        )

        self.assert_compile(
            tuple_(table1.c.myid, table1.c.name).in_(
                [tuple_(table2.c.otherid, table2.c.othername)]
            ),
            "(mytable.myid, mytable.name) IN "
            "((myothertable.otherid, myothertable.othername))",
        )

        self.assert_compile(
            tuple_(table1.c.myid, table1.c.name).in_(
                select([table2.c.otherid, table2.c.othername])
            ),
            "(mytable.myid, mytable.name) IN (SELECT "
            "myothertable.otherid, myothertable.othername FROM myothertable)",
        )

    def test_expanding_parameter(self):
        self.assert_compile(
            tuple_(table1.c.myid, table1.c.name).in_(
                bindparam("foo", expanding=True)
            ),
            "(mytable.myid, mytable.name) IN ([POSTCOMPILE_foo])",
        )

        dialect = default.DefaultDialect()
        dialect.tuple_in_values = True
        self.assert_compile(
            tuple_(table1.c.myid, table1.c.name).in_(
                bindparam("foo", expanding=True)
            ),
            "(mytable.myid, mytable.name) IN ([POSTCOMPILE_foo])",
            dialect=dialect,
        )

        self.assert_compile(
            table1.c.myid.in_(bindparam("foo", expanding=True)),
            "mytable.myid IN ([POSTCOMPILE_foo])",
        )

    def test_limit_offset_select_literal_binds(self):
        stmt = select([1]).limit(5).offset(6)
        self.assert_compile(
            stmt, "SELECT 1 LIMIT 5 OFFSET 6", literal_binds=True
        )

    def test_limit_offset_compound_select_literal_binds(self):
        stmt = select([1]).union(select([2])).limit(5).offset(6)
        self.assert_compile(
            stmt,
            "SELECT 1 UNION SELECT 2 LIMIT 5 OFFSET 6",
            literal_binds=True,
        )

    def test_multiple_col_binds(self):
        self.assert_compile(
            select(
                [literal_column("*")],
                or_(
                    table1.c.myid == 12,
                    table1.c.myid == "asdf",
                    table1.c.myid == "foo",
                ),
            ),
            "SELECT * FROM mytable WHERE mytable.myid = :myid_1 "
            "OR mytable.myid = :myid_2 OR mytable.myid = :myid_3",
        )

    def test_render_binds_as_literal(self):
        """test a compiler that renders binds inline into
        SQL in the columns clause."""

        dialect = default.DefaultDialect()

        class Compiler(dialect.statement_compiler):
            ansi_bind_rules = True

        dialect.statement_compiler = Compiler

        self.assert_compile(
            select([literal("someliteral")]),
            "SELECT 'someliteral' AS anon_1",
            dialect=dialect,
        )

        self.assert_compile(
            select([table1.c.myid + 3]),
            "SELECT mytable.myid + 3 AS anon_1 FROM mytable",
            dialect=dialect,
        )

        self.assert_compile(
            select([table1.c.myid.in_([4, 5, 6])]),
            "SELECT mytable.myid IN (4, 5, 6) AS anon_1 FROM mytable",
            dialect=dialect,
        )

        self.assert_compile(
            select([func.mod(table1.c.myid, 5)]),
            "SELECT mod(mytable.myid, 5) AS mod_1 FROM mytable",
            dialect=dialect,
        )

        self.assert_compile(
            select([literal("foo").in_([])]),
            "SELECT 1 != 1 AS anon_1",
            dialect=dialect,
        )

        self.assert_compile(
            select([literal(util.b("foo"))]),
            "SELECT 'foo' AS anon_1",
            dialect=dialect,
        )

        # test callable
        self.assert_compile(
            select([table1.c.myid == bindparam("foo", callable_=lambda: 5)]),
            "SELECT mytable.myid = 5 AS anon_1 FROM mytable",
            dialect=dialect,
        )

        empty_in_dialect = default.DefaultDialect(empty_in_strategy="dynamic")
        empty_in_dialect.statement_compiler = Compiler

        assert_raises_message(
            exc.CompileError,
            "Bind parameter 'foo' without a "
            "renderable value not allowed here.",
            bindparam("foo").in_([]).compile,
            dialect=empty_in_dialect,
        )

    def test_render_literal_execute_parameter(self):
        self.assert_compile(
            select([table1.c.myid]).where(
                table1.c.myid == bindparam("foo", 5, literal_execute=True)
            ),
            "SELECT mytable.myid FROM mytable "
            "WHERE mytable.myid = [POSTCOMPILE_foo]",
        )

    def test_render_literal_execute_parameter_literal_binds(self):
        self.assert_compile(
            select([table1.c.myid]).where(
                table1.c.myid == bindparam("foo", 5, literal_execute=True)
            ),
            "SELECT mytable.myid FROM mytable " "WHERE mytable.myid = 5",
            literal_binds=True,
        )

    def test_render_expanding_parameter(self):
        self.assert_compile(
            select([table1.c.myid]).where(
                table1.c.myid.in_(bindparam("foo", expanding=True))
            ),
            "SELECT mytable.myid FROM mytable "
            "WHERE mytable.myid IN ([POSTCOMPILE_foo])",
        )

    def test_render_expanding_parameter_literal_binds(self):
        self.assert_compile(
            select([table1.c.myid]).where(
                table1.c.myid.in_(bindparam("foo", [1, 2, 3], expanding=True))
            ),
            "SELECT mytable.myid FROM mytable "
            "WHERE mytable.myid IN (1, 2, 3)",
            literal_binds=True,
        )


class UnsupportedTest(fixtures.TestBase):
    def test_unsupported_element_str_visit_name(self):
        from sqlalchemy.sql.expression import ClauseElement

        class SomeElement(ClauseElement):
            __visit_name__ = "some_element"

        assert_raises_message(
            exc.UnsupportedCompilationError,
            r"Compiler <sqlalchemy.sql.compiler.StrSQLCompiler .*"
            r"can't render element of type <class '.*SomeElement'>",
            SomeElement().compile,
        )

    def test_unsupported_element_meth_visit_name(self):
        from sqlalchemy.sql.expression import ClauseElement

        class SomeElement(ClauseElement):
            @classmethod
            def __visit_name__(cls):
                return "some_element"

        assert_raises_message(
            exc.UnsupportedCompilationError,
            r"Compiler <sqlalchemy.sql.compiler.StrSQLCompiler .*"
            r"can't render element of type <class '.*SomeElement'>",
            SomeElement().compile,
        )

    def test_unsupported_operator(self):
        from sqlalchemy.sql.expression import BinaryExpression

        def myop(x, y):
            pass

        binary = BinaryExpression(column("foo"), column("bar"), myop)
        assert_raises_message(
            exc.UnsupportedCompilationError,
            r"Compiler <sqlalchemy.sql.compiler.StrSQLCompiler .*"
            r"can't render element of type <function.*",
            binary.compile,
        )


class StringifySpecialTest(fixtures.TestBase):
    def test_basic(self):
        stmt = select([table1]).where(table1.c.myid == 10)
        eq_ignore_whitespace(
            str(stmt),
            "SELECT mytable.myid, mytable.name, mytable.description "
            "FROM mytable WHERE mytable.myid = :myid_1",
        )

    def test_unnamed_column(self):
        stmt = Column(Integer) == 5
        eq_ignore_whitespace(str(stmt), '"<name unknown>" = :param_1')

    def test_cte(self):
        # stringify of these was supported anyway by defaultdialect.
        stmt = select([table1.c.myid]).cte()
        stmt = select([stmt])
        eq_ignore_whitespace(
            str(stmt),
            "WITH anon_1 AS (SELECT mytable.myid AS myid FROM mytable) "
            "SELECT anon_1.myid FROM anon_1",
        )

    def test_next_sequence_value(self):
        # using descriptive text that is intentionally not compatible
        # with any particular backend, since all backends have different
        # syntax

        seq = Sequence("my_sequence")

        eq_ignore_whitespace(
            str(seq.next_value()), "<next sequence value: my_sequence>"
        )

    def test_returning(self):
        stmt = table1.insert().returning(table1.c.myid)

        eq_ignore_whitespace(
            str(stmt),
            "INSERT INTO mytable (myid, name, description) "
            "VALUES (:myid, :name, :description) RETURNING mytable.myid",
        )

    def test_array_index(self):
        stmt = select([column("foo", types.ARRAY(Integer))[5]])

        eq_ignore_whitespace(str(stmt), "SELECT foo[:foo_1] AS anon_1")

    def test_unknown_type(self):
        class MyType(types.TypeEngine):
            __visit_name__ = "mytype"

        stmt = select([cast(table1.c.myid, MyType)])

        eq_ignore_whitespace(
            str(stmt),
            "SELECT CAST(mytable.myid AS MyType) AS myid FROM mytable",
        )

    def test_within_group(self):
        # stringify of these was supported anyway by defaultdialect.
        from sqlalchemy import within_group

        stmt = select(
            [
                table1.c.myid,
                within_group(func.percentile_cont(0.5), table1.c.name.desc()),
            ]
        )
        eq_ignore_whitespace(
            str(stmt),
            "SELECT mytable.myid, percentile_cont(:percentile_cont_1) "
            "WITHIN GROUP (ORDER BY mytable.name DESC) AS anon_1 FROM mytable",
        )


class KwargPropagationTest(fixtures.TestBase):
    @classmethod
    def setup_class(cls):
        from sqlalchemy.sql.expression import ColumnClause, TableClause

        class CatchCol(ColumnClause):
            pass

        class CatchTable(TableClause):
            pass

        cls.column = CatchCol("x")
        cls.table = CatchTable("y")
        cls.criterion = cls.column == CatchCol("y")

        @compiles(CatchCol)
        def compile_col(element, compiler, **kw):
            assert "canary" in kw
            return compiler.visit_column(element)

        @compiles(CatchTable)
        def compile_table(element, compiler, **kw):
            assert "canary" in kw
            return compiler.visit_table(element)

    def _do_test(self, element):
        d = default.DefaultDialect()
        d.statement_compiler(d, element, compile_kwargs={"canary": True})

    def test_binary(self):
        self._do_test(self.column == 5)

    def test_select(self):
        s = (
            select([self.column])
            .select_from(self.table)
            .where(self.column == self.criterion)
            .order_by(self.column)
        )
        self._do_test(s)

    def test_case(self):
        c = case([(self.criterion, self.column)], else_=self.column)
        self._do_test(c)

    def test_cast(self):
        c = cast(self.column, Integer)
        self._do_test(c)


class ExecutionOptionsTest(fixtures.TestBase):
    def test_non_dml(self):
        stmt = table1.select()
        compiled = stmt.compile()

        eq_(compiled.execution_options, {})

    def test_dml(self):
        stmt = table1.insert()
        compiled = stmt.compile()

        eq_(compiled.execution_options, {"autocommit": True})

    def test_embedded_element_true_to_none(self):
        stmt = table1.insert().cte()
        eq_(stmt._execution_options, {"autocommit": True})
        s2 = select([table1]).select_from(stmt)
        eq_(s2._execution_options, {})

        compiled = s2.compile()
        eq_(compiled.execution_options, {"autocommit": True})

    def test_embedded_element_true_to_false(self):
        stmt = table1.insert().cte()
        eq_(stmt._execution_options, {"autocommit": True})
        s2 = (
            select([table1])
            .select_from(stmt)
            .execution_options(autocommit=False)
        )
        eq_(s2._execution_options, {"autocommit": False})

        compiled = s2.compile()
        eq_(compiled.execution_options, {"autocommit": False})


class DDLTest(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = "default"

    def _illegal_type_fixture(self):
        class MyType(types.TypeEngine):
            pass

        @compiles(MyType)
        def compile_(element, compiler, **kw):
            raise exc.CompileError("Couldn't compile type")

        return MyType

    def test_reraise_of_column_spec_issue(self):
        MyType = self._illegal_type_fixture()
        t1 = Table("t", MetaData(), Column("x", MyType()))
        assert_raises_message(
            exc.CompileError,
            r"\(in table 't', column 'x'\): Couldn't compile type",
            schema.CreateTable(t1).compile,
        )

    def test_reraise_of_column_spec_issue_unicode(self):
        MyType = self._illegal_type_fixture()
        t1 = Table("t", MetaData(), Column(u("méil"), MyType()))
        assert_raises_message(
            exc.CompileError,
            u(r"\(in table 't', column 'méil'\): Couldn't compile type"),
            schema.CreateTable(t1).compile,
        )

    def test_system_flag(self):
        m = MetaData()
        t = Table(
            "t",
            m,
            Column("x", Integer),
            Column("y", Integer, system=True),
            Column("z", Integer),
        )
        self.assert_compile(
            schema.CreateTable(t), "CREATE TABLE t (x INTEGER, z INTEGER)"
        )
        m2 = MetaData()
        t2 = t.tometadata(m2)
        self.assert_compile(
            schema.CreateTable(t2), "CREATE TABLE t (x INTEGER, z INTEGER)"
        )

    def test_composite_pk_constraint_autoinc_first_implicit(self):
        m = MetaData()
        t = Table(
            "t",
            m,
            Column("a", Integer, primary_key=True),
            Column("b", Integer, primary_key=True, autoincrement=True),
        )
        self.assert_compile(
            schema.CreateTable(t),
            "CREATE TABLE t ("
            "a INTEGER NOT NULL, "
            "b INTEGER NOT NULL, "
            "PRIMARY KEY (b, a))",
        )

    def test_composite_pk_constraint_maintains_order_explicit(self):
        m = MetaData()
        t = Table(
            "t",
            m,
            Column("a", Integer),
            Column("b", Integer, autoincrement=True),
            schema.PrimaryKeyConstraint("a", "b"),
        )
        self.assert_compile(
            schema.CreateTable(t),
            "CREATE TABLE t ("
            "a INTEGER NOT NULL, "
            "b INTEGER NOT NULL, "
            "PRIMARY KEY (a, b))",
        )

    def test_create_table_suffix(self):
        class MyDialect(default.DefaultDialect):
            class MyCompiler(compiler.DDLCompiler):
                def create_table_suffix(self, table):
                    return "SOME SUFFIX"

            ddl_compiler = MyCompiler

        m = MetaData()
        t1 = Table("t1", m, Column("q", Integer))
        self.assert_compile(
            schema.CreateTable(t1),
            "CREATE TABLE t1 SOME SUFFIX (q INTEGER)",
            dialect=MyDialect(),
        )

    def test_table_no_cols(self):
        m = MetaData()
        t1 = Table("t1", m)
        self.assert_compile(schema.CreateTable(t1), "CREATE TABLE t1 ()")

    def test_table_no_cols_w_constraint(self):
        m = MetaData()
        t1 = Table("t1", m, CheckConstraint("a = 1"))
        self.assert_compile(
            schema.CreateTable(t1), "CREATE TABLE t1 (CHECK (a = 1))"
        )

    def test_table_one_col_w_constraint(self):
        m = MetaData()
        t1 = Table("t1", m, Column("q", Integer), CheckConstraint("a = 1"))
        self.assert_compile(
            schema.CreateTable(t1),
            "CREATE TABLE t1 (q INTEGER, CHECK (a = 1))",
        )

    def test_schema_translate_map_table(self):
        m = MetaData()
        t1 = Table("t1", m, Column("q", Integer))
        t2 = Table("t2", m, Column("q", Integer), schema="foo")
        t3 = Table("t3", m, Column("q", Integer), schema="bar")

        schema_translate_map = {None: "z", "bar": None, "foo": "bat"}

        self.assert_compile(
            schema.CreateTable(t1),
            "CREATE TABLE z.t1 (q INTEGER)",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            schema.CreateTable(t2),
            "CREATE TABLE bat.t2 (q INTEGER)",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            schema.CreateTable(t3),
            "CREATE TABLE t3 (q INTEGER)",
            schema_translate_map=schema_translate_map,
        )

    def test_schema_translate_map_sequence(self):
        s1 = schema.Sequence("s1")
        s2 = schema.Sequence("s2", schema="foo")
        s3 = schema.Sequence("s3", schema="bar")

        schema_translate_map = {None: "z", "bar": None, "foo": "bat"}

        self.assert_compile(
            schema.CreateSequence(s1),
            "CREATE SEQUENCE z.s1",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            schema.CreateSequence(s2),
            "CREATE SEQUENCE bat.s2",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            schema.CreateSequence(s3),
            "CREATE SEQUENCE s3",
            schema_translate_map=schema_translate_map,
        )

    def test_fk_render(self):
        a = Table("a", MetaData(), Column("q", Integer))
        b = Table("b", MetaData(), Column("p", Integer))

        self.assert_compile(
            schema.AddConstraint(
                schema.ForeignKeyConstraint([a.c.q], [b.c.p])
            ),
            "ALTER TABLE a ADD FOREIGN KEY(q) REFERENCES b (p)",
        )

        self.assert_compile(
            schema.AddConstraint(
                schema.ForeignKeyConstraint(
                    [a.c.q], [b.c.p], onupdate="SET NULL", ondelete="CASCADE"
                )
            ),
            "ALTER TABLE a ADD FOREIGN KEY(q) REFERENCES b (p) "
            "ON DELETE CASCADE ON UPDATE SET NULL",
        )

        self.assert_compile(
            schema.AddConstraint(
                schema.ForeignKeyConstraint(
                    [a.c.q], [b.c.p], initially="DEFERRED"
                )
            ),
            "ALTER TABLE a ADD FOREIGN KEY(q) REFERENCES b (p) "
            "INITIALLY DEFERRED",
        )

    def test_fk_illegal_sql_phrases(self):
        a = Table("a", MetaData(), Column("q", Integer))
        b = Table("b", MetaData(), Column("p", Integer))

        for kw in ("onupdate", "ondelete", "initially"):
            for phrase in (
                "NOT SQL",
                "INITALLY NOT SQL",
                "FOO RESTRICT",
                "CASCADE WRONG",
                "SET  NULL",
            ):
                const = schema.AddConstraint(
                    schema.ForeignKeyConstraint(
                        [a.c.q], [b.c.p], **{kw: phrase}
                    )
                )
                assert_raises_message(
                    exc.CompileError,
                    r"Unexpected SQL phrase: '%s'" % phrase,
                    const.compile,
                )


class SchemaTest(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = "default"

    def test_select(self):
        self.assert_compile(
            table4.select(),
            "SELECT remote_owner.remotetable.rem_id, "
            "remote_owner.remotetable.datatype_id,"
            " remote_owner.remotetable.value "
            "FROM remote_owner.remotetable",
        )

        self.assert_compile(
            table4.select(
                and_(table4.c.datatype_id == 7, table4.c.value == "hi")
            ),
            "SELECT remote_owner.remotetable.rem_id, "
            "remote_owner.remotetable.datatype_id,"
            " remote_owner.remotetable.value "
            "FROM remote_owner.remotetable WHERE "
            "remote_owner.remotetable.datatype_id = :datatype_id_1 AND"
            " remote_owner.remotetable.value = :value_1",
        )

        s = table4.select(
            and_(table4.c.datatype_id == 7, table4.c.value == "hi"),
            use_labels=True,
        )
        self.assert_compile(
            s,
            "SELECT remote_owner.remotetable.rem_id AS"
            " remote_owner_remotetable_rem_id, "
            "remote_owner.remotetable.datatype_id AS"
            " remote_owner_remotetable_datatype_id, "
            "remote_owner.remotetable.value "
            "AS remote_owner_remotetable_value FROM "
            "remote_owner.remotetable WHERE "
            "remote_owner.remotetable.datatype_id = :datatype_id_1 AND "
            "remote_owner.remotetable.value = :value_1",
        )

        # multi-part schema name
        self.assert_compile(
            table5.select(),
            'SELECT "dbo.remote_owner".remotetable.rem_id, '
            '"dbo.remote_owner".remotetable.datatype_id, '
            '"dbo.remote_owner".remotetable.value '
            'FROM "dbo.remote_owner".remotetable',
        )

        # multi-part schema name labels - convert '.' to '_'
        self.assert_compile(
            table5.select(use_labels=True),
            'SELECT "dbo.remote_owner".remotetable.rem_id AS'
            " dbo_remote_owner_remotetable_rem_id, "
            '"dbo.remote_owner".remotetable.datatype_id'
            " AS dbo_remote_owner_remotetable_datatype_id,"
            ' "dbo.remote_owner".remotetable.value AS '
            "dbo_remote_owner_remotetable_value FROM"
            ' "dbo.remote_owner".remotetable',
        )

    def test_schema_translate_select(self):
        m = MetaData()
        table1 = Table(
            "mytable",
            m,
            Column("myid", Integer),
            Column("name", String),
            Column("description", String),
        )
        schema_translate_map = {"remote_owner": "foob", None: "bar"}

        self.assert_compile(
            table1.select().where(table1.c.name == "hi"),
            "SELECT bar.mytable.myid, bar.mytable.name, "
            "bar.mytable.description FROM bar.mytable "
            "WHERE bar.mytable.name = :name_1",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            table4.select().where(table4.c.value == "hi"),
            "SELECT foob.remotetable.rem_id, foob.remotetable.datatype_id, "
            "foob.remotetable.value FROM foob.remotetable "
            "WHERE foob.remotetable.value = :value_1",
            schema_translate_map=schema_translate_map,
        )

        schema_translate_map = {"remote_owner": "foob"}
        self.assert_compile(
            select([table1, table4]).select_from(
                join(table1, table4, table1.c.myid == table4.c.rem_id)
            ),
            "SELECT mytable.myid, mytable.name, mytable.description, "
            "foob.remotetable.rem_id, foob.remotetable.datatype_id, "
            "foob.remotetable.value FROM mytable JOIN foob.remotetable "
            "ON mytable.myid = foob.remotetable.rem_id",
            schema_translate_map=schema_translate_map,
        )

    def test_schema_translate_aliases(self):
        schema_translate_map = {None: "bar"}

        m = MetaData()
        table1 = Table(
            "mytable",
            m,
            Column("myid", Integer),
            Column("name", String),
            Column("description", String),
        )
        table2 = Table(
            "myothertable",
            m,
            Column("otherid", Integer),
            Column("othername", String),
        )

        alias = table1.alias()

        stmt = (
            select([table2, alias])
            .select_from(table2.join(alias, table2.c.otherid == alias.c.myid))
            .where(alias.c.name == "foo")
        )

        self.assert_compile(
            stmt,
            "SELECT bar.myothertable.otherid, bar.myothertable.othername, "
            "mytable_1.myid, mytable_1.name, mytable_1.description "
            "FROM bar.myothertable JOIN bar.mytable AS mytable_1 "
            "ON bar.myothertable.otherid = mytable_1.myid "
            "WHERE mytable_1.name = :name_1",
            schema_translate_map=schema_translate_map,
        )

    def test_schema_translate_crud(self):
        schema_translate_map = {"remote_owner": "foob", None: "bar"}

        m = MetaData()
        table1 = Table(
            "mytable",
            m,
            Column("myid", Integer),
            Column("name", String),
            Column("description", String),
        )

        self.assert_compile(
            table1.insert().values(description="foo"),
            "INSERT INTO bar.mytable (description) VALUES (:description)",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            table1.update()
            .where(table1.c.name == "hi")
            .values(description="foo"),
            "UPDATE bar.mytable SET description=:description "
            "WHERE bar.mytable.name = :name_1",
            schema_translate_map=schema_translate_map,
        )
        self.assert_compile(
            table1.delete().where(table1.c.name == "hi"),
            "DELETE FROM bar.mytable WHERE bar.mytable.name = :name_1",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            table4.insert().values(value="there"),
            "INSERT INTO foob.remotetable (value) VALUES (:value)",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            table4.update()
            .where(table4.c.value == "hi")
            .values(value="there"),
            "UPDATE foob.remotetable SET value=:value "
            "WHERE foob.remotetable.value = :value_1",
            schema_translate_map=schema_translate_map,
        )

        self.assert_compile(
            table4.delete().where(table4.c.value == "hi"),
            "DELETE FROM foob.remotetable WHERE "
            "foob.remotetable.value = :value_1",
            schema_translate_map=schema_translate_map,
        )

    def test_alias(self):
        a = alias(table4, "remtable")
        self.assert_compile(
            a.select(a.c.datatype_id == 7),
            "SELECT remtable.rem_id, remtable.datatype_id, "
            "remtable.value FROM"
            " remote_owner.remotetable AS remtable "
            "WHERE remtable.datatype_id = :datatype_id_1",
        )

    def test_update(self):
        self.assert_compile(
            table4.update(
                table4.c.value == "test", values={table4.c.datatype_id: 12}
            ),
            "UPDATE remote_owner.remotetable SET datatype_id=:datatype_id "
            "WHERE remote_owner.remotetable.value = :value_1",
        )

    def test_insert(self):
        self.assert_compile(
            table4.insert(values=(2, 5, "test")),
            "INSERT INTO remote_owner.remotetable "
            "(rem_id, datatype_id, value) VALUES "
            "(:rem_id, :datatype_id, :value)",
        )


class CorrelateTest(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = "default"

    def test_dont_overcorrelate(self):
        self.assert_compile(
            select([table1])
            .select_from(table1)
            .select_from(table1.select().subquery()),
            "SELECT mytable.myid, mytable.name, "
            "mytable.description FROM mytable, (SELECT "
            "mytable.myid AS myid, mytable.name AS "
            "name, mytable.description AS description "
            "FROM mytable) AS anon_1",
        )

    def _fixture(self):
        t1 = table("t1", column("a"))
        t2 = table("t2", column("a"))
        return t1, t2, select([t1]).where(t1.c.a == t2.c.a)

    def _assert_where_correlated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a FROM t2 WHERE t2.a = "
            "(SELECT t1.a FROM t1 WHERE t1.a = t2.a)",
        )

    def _assert_where_all_correlated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t1.a, t2.a FROM t1, t2 WHERE t2.a = "
            "(SELECT t1.a WHERE t1.a = t2.a)",
        )

    # note there's no more "backwards" correlation after
    # we've done #2746
    # def _assert_where_backwards_correlated(self, stmt):
    #    self.assert_compile(
    #            stmt,
    #            "SELECT t2.a FROM t2 WHERE t2.a = "
    #            "(SELECT t1.a FROM t2 WHERE t1.a = t2.a)")

    # def _assert_column_backwards_correlated(self, stmt):
    #    self.assert_compile(stmt,
    #            "SELECT t2.a, (SELECT t1.a FROM t2 WHERE t1.a = t2.a) "
    #            "AS anon_1 FROM t2")

    def _assert_column_correlated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a, (SELECT t1.a FROM t1 WHERE t1.a = t2.a) "
            "AS anon_1 FROM t2",
        )

    def _assert_column_all_correlated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t1.a, t2.a, "
            "(SELECT t1.a WHERE t1.a = t2.a) AS anon_1 FROM t1, t2",
        )

    def _assert_having_correlated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a FROM t2 HAVING t2.a = "
            "(SELECT t1.a FROM t1 WHERE t1.a = t2.a)",
        )

    def _assert_from_uncorrelated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a, anon_1.a FROM t2, "
            "(SELECT t1.a AS a FROM t1, t2 WHERE t1.a = t2.a) AS anon_1",
        )

    def _assert_from_all_uncorrelated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t1.a, t2.a, anon_1.a FROM t1, t2, "
            "(SELECT t1.a AS a FROM t1, t2 WHERE t1.a = t2.a) AS anon_1",
        )

    def _assert_where_uncorrelated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a FROM t2 WHERE t2.a = "
            "(SELECT t1.a FROM t1, t2 WHERE t1.a = t2.a)",
        )

    def _assert_column_uncorrelated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a, (SELECT t1.a FROM t1, t2 "
            "WHERE t1.a = t2.a) AS anon_1 FROM t2",
        )

    def _assert_having_uncorrelated(self, stmt):
        self.assert_compile(
            stmt,
            "SELECT t2.a FROM t2 HAVING t2.a = "
            "(SELECT t1.a FROM t1, t2 WHERE t1.a = t2.a)",
        )

    def _assert_where_single_full_correlated(self, stmt):
        self.assert_compile(
            stmt, "SELECT t1.a FROM t1 WHERE t1.a = (SELECT t1.a)"
        )

    def test_correlate_semiauto_where(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_correlated(
            select([t2]).where(t2.c.a == s1.correlate(t2).scalar_subquery())
        )

    def test_correlate_semiauto_column(self):
        t1, t2, s1 = self._fixture()
        self._assert_column_correlated(
            select([t2, s1.correlate(t2).scalar_subquery()])
        )

    def test_correlate_semiauto_from(self):
        t1, t2, s1 = self._fixture()
        self._assert_from_uncorrelated(select([t2, s1.correlate(t2).alias()]))

    def test_correlate_semiauto_having(self):
        t1, t2, s1 = self._fixture()
        self._assert_having_correlated(
            select([t2]).having(t2.c.a == s1.correlate(t2).scalar_subquery())
        )

    def test_correlate_except_inclusion_where(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_correlated(
            select([t2]).where(
                t2.c.a == s1.correlate_except(t1).scalar_subquery()
            )
        )

    def test_correlate_except_exclusion_where(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_uncorrelated(
            select([t2]).where(
                t2.c.a == s1.correlate_except(t2).scalar_subquery()
            )
        )

    def test_correlate_except_inclusion_column(self):
        t1, t2, s1 = self._fixture()
        self._assert_column_correlated(
            select([t2, s1.correlate_except(t1).scalar_subquery()])
        )

    def test_correlate_except_exclusion_column(self):
        t1, t2, s1 = self._fixture()
        self._assert_column_uncorrelated(
            select([t2, s1.correlate_except(t2).scalar_subquery()])
        )

    def test_correlate_except_inclusion_from(self):
        t1, t2, s1 = self._fixture()
        self._assert_from_uncorrelated(
            select([t2, s1.correlate_except(t1).alias()])
        )

    def test_correlate_except_exclusion_from(self):
        t1, t2, s1 = self._fixture()
        self._assert_from_uncorrelated(
            select([t2, s1.correlate_except(t2).alias()])
        )

    def test_correlate_except_none(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_all_correlated(
            select([t1, t2]).where(
                t2.c.a == s1.correlate_except(None).scalar_subquery()
            )
        )

    def test_correlate_except_having(self):
        t1, t2, s1 = self._fixture()
        self._assert_having_correlated(
            select([t2]).having(
                t2.c.a == s1.correlate_except(t1).scalar_subquery()
            )
        )

    def test_correlate_auto_where(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_correlated(
            select([t2]).where(t2.c.a == s1.scalar_subquery())
        )

    def test_correlate_auto_column(self):
        t1, t2, s1 = self._fixture()
        self._assert_column_correlated(select([t2, s1.scalar_subquery()]))

    def test_correlate_auto_from(self):
        t1, t2, s1 = self._fixture()
        self._assert_from_uncorrelated(select([t2, s1.alias()]))

    def test_correlate_auto_having(self):
        t1, t2, s1 = self._fixture()
        self._assert_having_correlated(
            select([t2]).having(t2.c.a == s1.scalar_subquery())
        )

    def test_correlate_disabled_where(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_uncorrelated(
            select([t2]).where(t2.c.a == s1.correlate(None).scalar_subquery())
        )

    def test_correlate_disabled_column(self):
        t1, t2, s1 = self._fixture()
        self._assert_column_uncorrelated(
            select([t2, s1.correlate(None).scalar_subquery()])
        )

    def test_correlate_disabled_from(self):
        t1, t2, s1 = self._fixture()
        self._assert_from_uncorrelated(
            select([t2, s1.correlate(None).alias()])
        )

    def test_correlate_disabled_having(self):
        t1, t2, s1 = self._fixture()
        self._assert_having_uncorrelated(
            select([t2]).having(t2.c.a == s1.correlate(None).scalar_subquery())
        )

    def test_correlate_all_where(self):
        t1, t2, s1 = self._fixture()
        self._assert_where_all_correlated(
            select([t1, t2]).where(
                t2.c.a == s1.correlate(t1, t2).scalar_subquery()
            )
        )

    def test_correlate_all_column(self):
        t1, t2, s1 = self._fixture()
        self._assert_column_all_correlated(
            select([t1, t2, s1.correlate(t1, t2).scalar_subquery()])
        )

    def test_correlate_all_from(self):
        t1, t2, s1 = self._fixture()
        self._assert_from_all_uncorrelated(
            select([t1, t2, s1.correlate(t1, t2).alias()])
        )

    def test_correlate_where_all_unintentional(self):
        t1, t2, s1 = self._fixture()
        assert_raises_message(
            exc.InvalidRequestError,
            "returned no FROM clauses due to auto-correlation",
            select([t1, t2]).where(t2.c.a == s1.scalar_subquery()).compile,
        )

    def test_correlate_from_all_ok(self):
        t1, t2, s1 = self._fixture()
        self.assert_compile(
            select([t1, t2, s1.subquery()]),
            "SELECT t1.a, t2.a, anon_1.a FROM t1, t2, "
            "(SELECT t1.a AS a FROM t1, t2 WHERE t1.a = t2.a) AS anon_1",
        )

    def test_correlate_auto_where_singlefrom(self):
        t1, t2, s1 = self._fixture()
        s = select([t1.c.a])
        s2 = select([t1]).where(t1.c.a == s.scalar_subquery())
        self.assert_compile(
            s2, "SELECT t1.a FROM t1 WHERE t1.a = " "(SELECT t1.a FROM t1)"
        )

    def test_correlate_semiauto_where_singlefrom(self):
        t1, t2, s1 = self._fixture()

        s = select([t1.c.a])

        s2 = select([t1]).where(t1.c.a == s.correlate(t1).scalar_subquery())
        self._assert_where_single_full_correlated(s2)

    def test_correlate_except_semiauto_where_singlefrom(self):
        t1, t2, s1 = self._fixture()

        s = select([t1.c.a])

        s2 = select([t1]).where(
            t1.c.a == s.correlate_except(t2).scalar_subquery()
        )
        self._assert_where_single_full_correlated(s2)

    def test_correlate_alone_noeffect(self):
        # new as of #2668
        t1, t2, s1 = self._fixture()
        self.assert_compile(
            s1.correlate(t1, t2), "SELECT t1.a FROM t1, t2 WHERE t1.a = t2.a"
        )

    def test_correlate_except_froms(self):
        # new as of #2748
        t1 = table("t1", column("a"))
        t2 = table("t2", column("a"), column("b"))
        s = select([t2.c.b]).where(t1.c.a == t2.c.a)
        s = s.correlate_except(t2).alias("s")

        s2 = select([func.foo(s.c.b)]).scalar_subquery()
        s3 = select([t1], order_by=s2)

        self.assert_compile(
            s3,
            "SELECT t1.a FROM t1 ORDER BY "
            "(SELECT foo(s.b) AS foo_1 FROM "
            "(SELECT t2.b AS b FROM t2 WHERE t1.a = t2.a) AS s)",
        )

    def test_multilevel_froms_correlation(self):
        # new as of #2748
        p = table("parent", column("id"))
        c = table("child", column("id"), column("parent_id"), column("pos"))

        s = (
            c.select()
            .where(c.c.parent_id == p.c.id)
            .order_by(c.c.pos)
            .limit(1)
        )
        s = s.correlate(p).subquery()

        s = exists().select_from(s).where(s.c.id == 1)
        s = select([p]).where(s)
        self.assert_compile(
            s,
            "SELECT parent.id FROM parent WHERE EXISTS (SELECT * "
            "FROM (SELECT child.id AS id, child.parent_id AS parent_id, "
            "child.pos AS pos FROM child WHERE child.parent_id = parent.id "
            "ORDER BY child.pos LIMIT :param_1) AS anon_1 "
            "WHERE anon_1.id = :id_1)",
        )

    def test_no_contextless_correlate_except(self):
        # new as of #2748

        t1 = table("t1", column("x"))
        t2 = table("t2", column("y"))
        t3 = table("t3", column("z"))

        s = (
            select([t1])
            .where(t1.c.x == t2.c.y)
            .where(t2.c.y == t3.c.z)
            .correlate_except(t1)
        )
        self.assert_compile(
            s, "SELECT t1.x FROM t1, t2, t3 WHERE t1.x = t2.y AND t2.y = t3.z"
        )

    def test_multilevel_implicit_correlation_disabled(self):
        # test that implicit correlation with multilevel WHERE correlation
        # behaves like 0.8.1, 0.7 (i.e. doesn't happen)
        t1 = table("t1", column("x"))
        t2 = table("t2", column("y"))
        t3 = table("t3", column("z"))

        s = select([t1.c.x]).where(t1.c.x == t2.c.y)
        s2 = select([t3.c.z]).where(t3.c.z == s.scalar_subquery())
        s3 = select([t1]).where(t1.c.x == s2.scalar_subquery())

        self.assert_compile(
            s3,
            "SELECT t1.x FROM t1 "
            "WHERE t1.x = (SELECT t3.z "
            "FROM t3 "
            "WHERE t3.z = (SELECT t1.x "
            "FROM t1, t2 "
            "WHERE t1.x = t2.y))",
        )

    def test_from_implicit_correlation_disabled(self):
        # test that implicit correlation with immediate and
        # multilevel FROM clauses behaves like 0.8.1 (i.e. doesn't happen)
        t1 = table("t1", column("x"))
        t2 = table("t2", column("y"))

        s = select([t1.c.x]).where(t1.c.x == t2.c.y)
        s2 = select([t2, s.subquery()])
        s3 = select([t1, s2.subquery()])

        self.assert_compile(
            s3,
            "SELECT t1.x, anon_1.y, anon_1.x FROM t1, "
            "(SELECT t2.y AS y, anon_2.x AS x FROM t2, "
            "(SELECT t1.x AS x FROM t1, t2 WHERE t1.x = t2.y) "
            "AS anon_2) AS anon_1",
        )


class CoercionTest(fixtures.TestBase, AssertsCompiledSQL):
    __dialect__ = default.DefaultDialect(supports_native_boolean=True)

    def _fixture(self):
        m = MetaData()
        return Table("foo", m, Column("id", Integer))

    bool_table = table("t", column("x", Boolean))

    def test_coerce_bool_where(self):
        self.assert_compile(
            select([self.bool_table]).where(self.bool_table.c.x),
            "SELECT t.x FROM t WHERE t.x",
        )

    def test_coerce_bool_where_non_native(self):
        self.assert_compile(
            select([self.bool_table]).where(self.bool_table.c.x),
            "SELECT t.x FROM t WHERE t.x = 1",
            dialect=default.DefaultDialect(supports_native_boolean=False),
        )

        self.assert_compile(
            select([self.bool_table]).where(~self.bool_table.c.x),
            "SELECT t.x FROM t WHERE t.x = 0",
            dialect=default.DefaultDialect(supports_native_boolean=False),
        )

    def test_val_and_false(self):
        t = self._fixture()
        self.assert_compile(and_(t.c.id == 1, False), "false")

    def test_val_and_true_coerced(self):
        t = self._fixture()
        self.assert_compile(and_(t.c.id == 1, True), "foo.id = :id_1")

    def test_val_is_null_coerced(self):
        t = self._fixture()
        self.assert_compile(and_(t.c.id == None), "foo.id IS NULL")  # noqa

    def test_val_and_None(self):
        t = self._fixture()
        self.assert_compile(and_(t.c.id == 1, None), "foo.id = :id_1 AND NULL")

    def test_None_and_val(self):
        t = self._fixture()
        self.assert_compile(and_(None, t.c.id == 1), "NULL AND foo.id = :id_1")

    def test_None_and_nothing(self):
        # current convention is None in and_()
        # returns None May want
        # to revise this at some point.
        self.assert_compile(and_(None), "NULL")

    def test_val_and_null(self):
        t = self._fixture()
        self.assert_compile(
            and_(t.c.id == 1, null()), "foo.id = :id_1 AND NULL"
        )


class ResultMapTest(fixtures.TestBase):

    """test the behavior of the 'entry stack' and the determination
    when the result_map needs to be populated.

    """

    def test_compound_populates(self):
        t = Table("t", MetaData(), Column("a", Integer), Column("b", Integer))
        stmt = select([t]).union(select([t]))
        comp = stmt.compile()
        eq_(
            comp._create_result_map(),
            {
                "a": ("a", (t.c.a, "a", "a"), t.c.a.type),
                "b": ("b", (t.c.b, "b", "b"), t.c.b.type),
            },
        )

    def test_compound_not_toplevel_doesnt_populate(self):
        t = Table("t", MetaData(), Column("a", Integer), Column("b", Integer))
        subq = select([t]).union(select([t])).subquery()
        stmt = select([t.c.a]).select_from(t.join(subq, t.c.a == subq.c.a))
        comp = stmt.compile()
        eq_(
            comp._create_result_map(),
            {"a": ("a", (t.c.a, "a", "a"), t.c.a.type)},
        )

    def test_compound_only_top_populates(self):
        t = Table("t", MetaData(), Column("a", Integer), Column("b", Integer))
        stmt = select([t.c.a]).union(select([t.c.b]))
        comp = stmt.compile()
        eq_(
            comp._create_result_map(),
            {"a": ("a", (t.c.a, "a", "a"), t.c.a.type)},
        )

    def test_label_plus_element(self):
        t = Table("t", MetaData(), Column("a", Integer))
        l1 = t.c.a.label("bar")
        tc = type_coerce(t.c.a + "str", String)
        stmt = select([t.c.a, l1, tc])
        comp = stmt.compile()
        tc_anon_label = comp._create_result_map()["anon_1"][1][0]
        eq_(
            comp._create_result_map(),
            {
                "a": ("a", (t.c.a, "a", "a"), t.c.a.type),
                "bar": ("bar", (l1, "bar"), l1.type),
                "anon_1": (
                    tc.anon_label,
                    (tc_anon_label, "anon_1", tc),
                    tc.type,
                ),
            },
        )

    def test_label_conflict_union(self):
        t1 = Table(
            "t1", MetaData(), Column("a", Integer), Column("b", Integer)
        )
        t2 = Table("t2", MetaData(), Column("t1_a", Integer))
        union = select([t2]).union(select([t2])).alias()

        t1_alias = t1.alias()
        stmt = (
            select([t1, t1_alias])
            .select_from(t1.join(union, t1.c.a == union.c.t1_a))
            .apply_labels()
        )
        comp = stmt.compile()
        eq_(
            set(comp._create_result_map()),
            set(["t1_1_b", "t1_1_a", "t1_a", "t1_b"]),
        )
        is_(comp._create_result_map()["t1_a"][1][2], t1.c.a)

    def test_insert_with_select_values(self):
        astring = Column("a", String)
        aint = Column("a", Integer)
        m = MetaData()
        Table("t1", m, astring)
        t2 = Table("t2", m, aint)

        stmt = t2.insert().values(a=select([astring])).returning(aint)
        comp = stmt.compile(dialect=postgresql.dialect())
        eq_(
            comp._create_result_map(),
            {"a": ("a", (aint, "a", "a"), aint.type)},
        )

    def test_insert_from_select(self):
        astring = Column("a", String)
        aint = Column("a", Integer)
        m = MetaData()
        Table("t1", m, astring)
        t2 = Table("t2", m, aint)

        stmt = (
            t2.insert().from_select(["a"], select([astring])).returning(aint)
        )
        comp = stmt.compile(dialect=postgresql.dialect())
        eq_(
            comp._create_result_map(),
            {"a": ("a", (aint, "a", "a"), aint.type)},
        )

    def test_nested_api(self):
        from sqlalchemy.engine.result import ResultMetaData

        stmt2 = select([table2]).subquery()

        stmt1 = select([table1]).select_from(stmt2)

        contexts = {}

        int_ = Integer()

        class MyCompiler(compiler.SQLCompiler):
            def visit_select(self, stmt, *arg, **kw):

                if stmt is stmt2.element:
                    with self._nested_result() as nested:
                        contexts[stmt2.element] = nested
                        text = super(MyCompiler, self).visit_select(
                            stmt2.element
                        )
                        self._add_to_result_map("k1", "k1", (1, 2, 3), int_)
                else:
                    text = super(MyCompiler, self).visit_select(
                        stmt, *arg, **kw
                    )
                    self._add_to_result_map("k2", "k2", (3, 4, 5), int_)
                return text

        comp = MyCompiler(default.DefaultDialect(), stmt1)
        eq_(
            ResultMetaData._create_result_map(contexts[stmt2.element][0]),
            {
                "otherid": (
                    "otherid",
                    (table2.c.otherid, "otherid", "otherid"),
                    table2.c.otherid.type,
                ),
                "othername": (
                    "othername",
                    (table2.c.othername, "othername", "othername"),
                    table2.c.othername.type,
                ),
                "k1": ("k1", (1, 2, 3), int_),
            },
        )
        eq_(
            comp._create_result_map(),
            {
                "myid": (
                    "myid",
                    (table1.c.myid, "myid", "myid"),
                    table1.c.myid.type,
                ),
                "k2": ("k2", (3, 4, 5), int_),
                "name": (
                    "name",
                    (table1.c.name, "name", "name"),
                    table1.c.name.type,
                ),
                "description": (
                    "description",
                    (table1.c.description, "description", "description"),
                    table1.c.description.type,
                ),
            },
        )

    def test_select_wraps_for_translate_ambiguity(self):
        # test for issue #3657
        t = table("a", column("x"), column("y"), column("z"))

        l1, l2, l3 = t.c.z.label("a"), t.c.x.label("b"), t.c.x.label("c")
        orig = [t.c.x, t.c.y, l1, l2, l3]
        stmt = select(orig)
        wrapped = stmt._generate()
        wrapped = wrapped.column(
            func.ROW_NUMBER().over(order_by=t.c.z)
        ).alias()

        wrapped_again = select([c for c in wrapped.c])

        compiled = wrapped_again.compile(
            compile_kwargs={"select_wraps_for": stmt}
        )

        proxied = [obj[0] for (k, n, obj, type_) in compiled._result_columns]
        for orig_obj, proxied_obj in zip(orig, proxied):
            is_(orig_obj, proxied_obj)

    def test_select_wraps_for_translate_ambiguity_dupe_cols(self):
        # test for issue #3657
        t = table("a", column("x"), column("y"), column("z"))

        l1, l2, l3 = t.c.z.label("a"), t.c.x.label("b"), t.c.x.label("c")

        orig = [t.c.x, t.c.y, l1, t.c.y, l2, t.c.x, l3]

        # create the statement with some duplicate columns.  right now
        # the behavior is that these redundant columns are deduped.
        stmt = select([t.c.x, t.c.y, l1, t.c.y, l2, t.c.x, l3])

        # so the statement has 7 inner columns...
        eq_(len(list(stmt.inner_columns)), 7)

        # 7 are exposed as of 1.4, no more deduping
        eq_(len(stmt.subquery().c), 7)

        # will render 7 as well
        eq_(len(stmt._columns_plus_names), 7)

        wrapped = stmt._generate()
        wrapped = wrapped.column(
            func.ROW_NUMBER().over(order_by=t.c.z)
        ).alias()

        # so when we wrap here we're going to have only 5 columns
        wrapped_again = select([c for c in wrapped.c])

        # so the compiler logic that matches up the "wrapper" to the
        # "select_wraps_for" can't use inner_columns to match because
        # these collections are not the same
        compiled = wrapped_again.compile(
            compile_kwargs={"select_wraps_for": stmt}
        )

        proxied = [obj[0] for (k, n, obj, type_) in compiled._result_columns]
        for orig_obj, proxied_obj in zip(orig, proxied):

            is_(orig_obj, proxied_obj)
