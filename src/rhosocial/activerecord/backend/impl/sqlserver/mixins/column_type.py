# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/column_type.py
"""SQL Server's answer to "which column class does this Python type mean here".

This is the **column** half of the ColumnTypeSupport protocol (the storage half
is :meth:`SQLServerDialect.suggested_data_types`), and it answers a different
question from that one. A column class says what a value can *do*; how it is
stored is the DDL layer's separate decision, and neither reads the other. Two
of SQL Server's most famous facts therefore stay **out** of the table below and
are stated here instead, so that their absence reads as a decision rather than
as an oversight:

* **``JSON``** is not a storage type on 2019 or 2022. A document is kept in
  ``NVARCHAR(MAX)`` and the *functions* are what make it a document --
  ``JSON_VALUE`` / ``JSON_QUERY`` / ``OPENJSON`` / ``ISJSON`` / ``JSON_MODIFY``,
  all of which arrived with 2016 and are measured working on 2019, 2022 and 2025
  (``suggested-pairing-json.md`` §"发现" items 3 and 7). SQL Server **2025** does
  have a native ``json`` word, and this backend does not model it yet: the
  catalog answers ``json`` with ``CHARACTER_MAXIMUM_LENGTH = -1`` and the parser
  returns ``CustomType('json')`` while ``format_data_type_json`` still renders
  ``NVARCHAR(MAX)`` (fix item #22, evidence in this repository's
  ``.claude/plan/2026-10-08/secondary-gaps-investigation.md`` 附录 F.4-6). None of
  that changes the column answer: a document carries the same operations
  wherever it is kept, and the storage spelling is
  :meth:`SQLServerDialect.suggested_data_types`'s business.
* **``UNIQUEIDENTIFIER``** is native, so nothing about the ``UUID`` cell is a
  substitute. What *is* unusual about it is its **order**: SQL Server sorts
  ``uniqueidentifier`` by its internal byte layout, not by the canonical text
  order -- measured on all three servers, ``ORDER BY u`` returns ``[2, 1, 3]``
  where the text order is ``[1, 2, 3]``, and the range predicate ``u > U2``
  matches a different set of rows for the same reason
  (``suggested-pairing-uuid.md`` §"发现" item 4 and the ordering item).
  ``CONVERT(varchar(36), u)`` restores the text order. That is a **rendering**
  obligation on whoever writes the formatter (Phase 2b), so it is recorded
  here and *not* narrowed: ordering works, it just needs a ``CONVERT`` to mean
  what it means elsewhere.

What does reach the table is SQL Server's lack of a **native array type** --
there is none on any version, so a column cannot be declared ``INT[]`` -- and
its two storage substitutions above. ``float`` / ``Decimal`` also stop being
one generic number at the **storage** layer, because ``FLOAT`` and
``DECIMAL(p,s)`` are two families with different rounding behaviour (measured:
``ROUND(2.675, 2)`` is ``2.68`` for ``decimal`` and ``2.67`` for ``float``,
``suggested-pairing-numeric.md`` §"发现" item 1). Core's column classes make the
same split impossible to express now: :class:`NumericColumn` is one class for
every numeric width and precision -- the operations are the same whatever the
value was declared as, and the difference between a ``NUMERIC(18,4)`` and a
``DOUBLE PRECISION`` belongs to the DDL layer's ``DataType``. So both entries
answer :class:`NumericColumn` here, and the measured two-roundings fact is
carried by the DataType declaration rather than dropped.

The table answers all eighteen of the framework's common Python types and needs
**no version gate**: the JSON route works on 2019, 2022 and 2025 alike, and the
three agree item for item. An entry left out would be indistinguishable from
one nobody thought about, so every key is present; the only permitted ``None``
is a genuine last resort saying "this backend has no column class for that value
family", and this table reaches none of them -- SQL Server's substitutions
carry every entry.

Evidence is the measured live-server sweep recorded in
``.claude/plan/2026-10-08/`` of the core repository
(``suggested-pairing-json.md``, ``suggested-pairing-array.md``,
``suggested-pairing-datetime.md``, ``suggested-pairing-string-enum.md``,
``suggested-pairing-uuid.md``, ``suggested-pairing-numeric.md`` §8.1 / §8.4),
against SQL Server 2019 CU32 (15.0.4465.1), 2022 CU24 (16.0.4250.1) and 2025 CU4
(17.0.4035.5).

One thing the sweep did **not** measure is the boolean family: the four-server
boolean probe (§7 of ``suggested-mappings.md``) ran against sqlite, MySQL,
MariaDB and PostgreSQL, and SQL Server was not in it. Since a narrowing needs a
measurement, nothing about ``BooleanColumn`` is declared -- neither
``is_true`` / ``is_false`` (T-SQL has no boolean literal to compare against)
nor the aggregate family. That is the honest state of the evidence, and it is
recorded here rather than left to be inferred from a cell that looks complete.
"""

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Type

from rhosocial.activerecord.backend.dialect.mixins.column_type import ColumnTypeMixin
from rhosocial.activerecord.backend.expression.column_types import (
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    TimestampColumn,
    UUIDColumn,
)

#: SQL Server's complete answer for every one of the framework's common Python
#: types: ``{common Python type: ColumnBase subclass}``.
#:
#: The deviations from the portable baseline are three groups, and each is a
#: fact about this server rather than a preference.
SQLSERVER_COLUMN_TYPES: Dict[Any, Type[ColumnBase]] = {
    # --- numbers ----------------------------------------------------------
    # §1 makes `float` the `FLOAT(53)` family and `Decimal` the `DECIMAL(p,s)`
    # family. SQL Server stores the two as distinct types and their arithmetic
    # differs: a `DECIMAL` is exact and a `FLOAT` is not, and the rounding
    # follows -- measured, `ROUND(2.675, 2)` gives `2.68` on a `decimal` column
    # and `2.67` on a `float` one (`suggested-pairing-numeric.md` §"发现" item
    # 1), where the other binary-float servers (sqlite REAL, MySQL) agree with
    # SQL Server's `float`. The column *class* cannot tell the two apart
    # any more: core has one NumericColumn for every numeric width and
    # precision, because the operations are the same either way and the
    # `NUMERIC(18,4)` / `DOUBLE PRECISION` difference is a DataType fact. So
    # both entries answer NumericColumn, and the measured two-roundings fact
    # rides with the DDL declaration rather than being lost.
    float: NumericColumn,
    decimal.Decimal: NumericColumn,
    # --- booleans ----------------------------------------------------------
    # `BIT`, which takes no width (`bit(1)` is refused with error 2716 --
    # this backend's own fix for it is in `parse_type`). Storage is `BIT`
    # and the column class is unaffected: `is_true` / `is_false` / `&` / `|`
    # / `~` and comparison are BooleanColumn's.
    bool: BooleanColumn,
    # --- integers ----------------------------------------------------------
    # `INT` in the width axis (`tinyint` .. `bigint`), with `unsigned` as no
    # concept at all: overflow behaviour rides with the DataType
    # declaration, not with a different operation surface. The whole-number
    # answer is the baseline every backend gives.
    int: IntegerColumn,
    # --- text and bytes ----------------------------------------------------
    # `NVARCHAR(n)`; this backend's default rendering is the Unicode dialect
    # (`VARCHAR` spells as `NVARCHAR`), which is a storage decision and
    # stays in `suggested_data_types`. Measured on all three versions:
    # `=` / `IN`, `LIKE` / `NOT LIKE`, concatenation, 1-based substring,
    # `UPPER` / `LOWER`, `TRIM` and `ORDER BY` all pass, and an over-long
    # value is **refused** (a truncation error, not a silent cut).
    str: StringColumn,
    # `VARBINARY(n)` / `VARBINARY(MAX)`; equality, byte length, byte
    # substring, concatenation and hex (`0x…`) were each measured present.
    # The read-back shape and the fact that `CONCAT` on bytes returns a
    # mis-decoded `str` (so `+` is the spelling) are value-layer facts.
    # Note that the fixed-length `BINARY(16)` word is **not modelled as a
    # type** (fix item #21, 附录 F.4-5 -- it parses to `CustomType`), which
    # is a storage gap: the column answer below is unaffected by it and
    # stays `BinaryColumn`.
    bytes: BinaryColumn,
    bytearray: BinaryColumn,
    # --- date / time -------------------------------------------------------
    # `DATE`, `TIME(p)`, `DATETIME2(p)` and `DATETIMEOFFSET(p)` are four
    # real storage types and TimestampColumn is the one class core has for
    # all of them; core has no DateColumn / TimeColumn yet, so this is the
    # shared baseline rather than a claim that the four are one type.
    # Measured: comparisons, `y/m/d/h/mi/s` extraction, `DATEADD` increments
    # and `datetime - datetime` (whole seconds, `DATEDIFF`) all work, and
    # `DATETIME2(7)` keeps microseconds. A tz-aware `datetime` normalises
    # to the same entry and both `AT TIME ZONE 'UTC'` directions were
    # measured working, so nothing about tz is narrowed.
    datetime.date: TimestampColumn,
    datetime.time: TimestampColumn,
    datetime.datetime: TimestampColumn,
    # A timedelta is a number of seconds here. SQL Server has no interval
    # *type* at all -- a span exists only as `DATEDIFF`, which is an
    # expression -- so a stored duration has to be a count, and the value
    # layer serialises to seconds because the driver refuses a bound
    # `timedelta` outright (`suggested-mappings.md` §8.2 item 4). There is
    # no `IntervalColumn` class yet, so this is the baseline every backend
    # without an interval type gives.
    datetime.timedelta: NumericColumn,
    # Native `UNIQUEIDENTIFIER` (there is also a documented `char(36)`
    # convention, which is a storage choice and not a column one). Measured:
    # `=` / `IN` work, prefix `LIKE` works, `NEWID()` is available in a
    # SELECT while `NEWSEQUENTIALID()` is a column default only, and the
    # value comes back as an **upper-case str** (a value-layer converter
    # item). Ordering is the documented exception -- see the module
    # docstring; it is a rendering obligation, not a missing operation.
    uuid.UUID: UUIDColumn,
    # --- documents ---------------------------------------------------------
    # `NVARCHAR(MAX)` holding JSON text, with the 2016 function family
    # making it a document. The whole measured battery passes on 2019,
    # 2022 and 2025 alike (`suggested-pairing-json.md` §"端级三态"): binding
    # a JSON text parameter, scalar and nested path extraction
    # (`JSON_VALUE` / `JSON_QUERY`), key existence (`OPENJSON` + `EXISTS`),
    # array length (counting `OPENJSON` rows), validity (`ISJSON`) and
    # document building. This is a **χ route** and says so: the column is
    # text, so whole-column equality is a comparison of serialized text, and
    # the semantically correct recipe is the count-plus-`JSON_VALUE` concat
    # rather than `=` on the document (`suggested-pairing-array.md` §"发现"
    # item 4a/4b). Both renderings are a Phase 2b obligation; the
    # operation itself exists on every measured version, so it is not
    # narrowed here.
    dict: JSONColumn,
    # --- arrays ------------------------------------------------------------
    # SQL Server has **no array type on any version** -- nothing can be
    # declared as an array, and `format_array_expression` raises with the
    # "use JSON or comma-separated values" suggestion. The operations a
    # sequence carries were measured present through the JSON route on all
    # three servers (`suggested-pairing-array.md` §A, the 2019 / 2022 /
    # 2025 row): array length by counting `OPENJSON`, element access via
    # `JSON_VALUE(doc, '$[n]')`, containment via `OPENJSON EXISTS`, unnest
    # via `CROSS APPLY OPENJSON`, and both text and concatenative
    # whole-column equality. `ArrayColumn`'s whole surface is
    # `array_length` / `unnest` over a *native* array -- a column this
    # server cannot declare -- so the suggestion follows the operations
    # that actually exist. The one gap in that battery is the quantifier
    # (`v = ANY(x)`), measured a **syntax error** here; it is an emulation
    # (`IN (SELECT CAST([value] AS INT) FROM OPENJSON)`) rather than an
    # operator, and belongs to Phase 2b.
    list: JSONColumn,
    # A tuple is heterogeneous and a set is de-duplicated by Python before
    # it ever reaches the server; neither changes the storage family, which
    # is a JSON document.
    tuple: JSONColumn,
    set: JSONColumn,
    frozenset: JSONColumn,
    # No native enum: the measured DDL is `NVARCHAR(20) CHECK (...)` with
    # an illegal member refused by the CHECK (a column without the CHECK
    # accepts it), `ORDER BY` in **lexicographic** order rather than
    # declaration order (which is the opposite of PostgreSQL's and
    # ClickHouse's native enum), and the value comes back as a `str`.
    # Those are storage and value-layer facts; the operation surface --
    # equality, `IN`, `ORDER BY` -- is StringColumn's.
    enum.Enum: StringColumn,
}


class SQLServerColumnTypeMixin(ColumnTypeMixin):
    """SQL Server's full 18-entry column-type table.

    Composed into :class:`~...dialect.SQLServerDialect` **ahead of** core's
    :class:`ColumnTypeMixin`, so its :meth:`suggested_column_types` is the one
    a model layer reaches. Core supplies no table of its own: an entry a
    dialect does not answer fails at resolution time, by name, rather than
    being filled in with a guess about a server core has never seen.

    The table is a class attribute because it does not vary by version: the
    measured 2019 / 2022 / 2025 sweep gives the same answer on all three.
    """

    def suggested_column_types(self) -> Dict[Any, Type[ColumnBase]]:
        """The column class each common Python type means on SQL Server.

        A fresh copy per call, so a caller mutating the answer cannot corrupt
        what the next lookup reads. All eighteen entries are answered with a
        class: SQL Server's storage substitutions (JSON documents in
        ``NVARCHAR(MAX)``, spans as counts, no native array) still carry the
        operations, so this table has no last-resort ``None``.
        """
        return dict(SQLSERVER_COLUMN_TYPES)


__all__ = ["SQLSERVER_COLUMN_TYPES", "SQLServerColumnTypeMixin"]
