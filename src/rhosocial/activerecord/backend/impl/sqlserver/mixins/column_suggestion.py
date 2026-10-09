# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/column_suggestion.py
"""SQL Server's answer to "which column class does this Python type mean here".

This is the **column** half of the suggestion protocol (the storage half is
:meth:`SQLServerDialect.suggested_data_types`), and it answers a different
question from that one. A column class says what a value can *do*; how it is
stored is the DDL layer's separate decision, and neither reads the
other. Two of SQL Server's most famous facts therefore stay **out** of the
table below and are stated here instead, so that their absence reads as a
decision rather than as an oversight:

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
one generic number, because ``FLOAT`` and ``DECIMAL(p,s)`` are two families
with different rounding behaviour (measured: ``ROUND(2.675, 2)`` is ``2.68`` for
``decimal`` and ``2.67`` for ``float``, ``suggested-pairing-numeric.md`` §"发现"
item 1).

The table answers all 18 entries of
:data:`~rhosocial.activerecord.backend.expression.column_suggestions.COLUMN_TYPE_ENTRIES`
and needs **no version gate**: the JSON route works on 2019, 2022 and 2025
alike, and the three agree item for item, so an entry that could branch has
nothing to branch on. An entry left out is indistinguishable from one nobody
thought about, and only the first of those is actionable; where a backend
genuinely has no answer the value is
:data:`~rhosocial.activerecord.backend.expression.column_suggestions.UNSUPPORTED`,
which resolution turns into a definition-time failure naming ``UseColumnType``.

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

from rhosocial.activerecord.backend.dialect.mixins.column_suggestion import (
    ColumnSuggestionMixin,
)
from rhosocial.activerecord.backend.expression.column_suggestions import (
    COLUMN_TYPE_ENTRIES,
)
from rhosocial.activerecord.backend.expression.column_types import (
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)

from .version_constants import SQL_SERVER_2016


class SQLServerColumnSuggestionMixin(ColumnSuggestionMixin):
    """SQL Server's full 18-entry column suggestion table, and its narrowing.

    Composed into :class:`~...dialect.SQLServerDialect` **ahead of** core's
    :class:`ColumnSuggestionMixin`, so its :meth:`suggested_column_types` and
    :meth:`supports_column_operation` are the ones a model layer reaches.

    The table is a class attribute because it does not vary by version: the
    measured 2019 / 2022 / 2025 sweep gives the same answer on all three, which
    is asserted rather than assumed by the contract tests.
    """

    #: SQL Server's complete answer for every entry of ``COLUMN_TYPE_ENTRIES``.
    #:
    #: The deviations from :data:`NEUTRAL_COLUMN_TYPE_SUGGESTIONS` are three
    #: groups, and each is a fact about this server rather than a preference.
    COLUMN_TYPE_SUGGESTIONS: Dict[Any, Type[ColumnBase]] = {
        # --- numbers core keeps together ------------------------------------
        # §1 makes `float` the `FLOAT(53)` family and `Decimal` the
        # `DECIMAL(p,s)` family. SQL Server stores the two as distinct types and
        # their arithmetic differs: a `DECIMAL` is exact and a `FLOAT` is not,
        # and the rounding follows -- measured, `ROUND(2.675, 2)` gives `2.68` on
        # a `decimal` column and `2.67` on a `float` one
        # (`suggested-pairing-numeric.md` §"发现" item 1), where the other
        # binary-float servers (sqlite REAL, MySQL) agree with SQL Server's
        # `float`. A class that cannot tell the two apart is not describing
        # this server's surface.
        float: FloatColumn,
        decimal.Decimal: DecimalColumn,
        # --- booleans ------------------------------------------------------
        # `BIT`, which takes no width (`bit(1)` is refused with error 2716 --
        # this backend's own fix for it is in `parse_type`). Storage is `BIT`
        # and the column class is unaffected: `is_true` / `is_false` / `&` / `|`
        # / `~` and comparison are BooleanColumn's.
        bool: BooleanColumn,
        # --- integers ------------------------------------------------------
        # `INT` in the width axis (`tinyint` .. `bigint`), with `unsigned` as no
        # concept at all: overflow behaviour rides with the DataType
        # declaration, not with a different operation surface. The whole-number
        # answer is the baseline every backend gives.
        int: IntegerColumn,
        # --- text and bytes ------------------------------------------------
        # `NVARCHAR(n)`; this backend's default rendering is the Unicode dialect
        # (`VARCHAR` spells as `NVARCHAR`), which is a storage decision and
        # stays in `suggested_data_types`. Measured on all three versions:
        # `=` / `IN`, `LIKE` / `NOT LIKE`, concatenation, 1-based substring,
        # `UPPER` / `LOWER`, `TRIM` and `ORDER BY` all pass, and an over-long
        # value is **refused** (a truncation error, not a silent cut).
        # `ilike` is the one narrowing -- see `supports_column_operation`.
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
        # --- date / time ---------------------------------------------------
        # `DATE`, `TIME(p)`, `DATETIME2(p)` and `DATETIMEOFFSET(p)` are four
        # real storage types and DateTimeColumn is the one class core has for
        # all of them; core has no DateColumn / TimeColumn yet, so this is the
        # shared baseline rather than a claim that the four are one type.
        # Measured: comparisons, `y/m/d/h/mi/s` extraction, `DATEADD` increments
        # and `datetime - datetime` (whole seconds, `DATEDIFF`) all work, and
        # `DATETIME2(7)` keeps microseconds. A tz-aware `datetime` normalises
        # to the same entry and both `AT TIME ZONE 'UTC'` directions were
        # measured working, so nothing about tz is narrowed.
        datetime.date: DateTimeColumn,
        datetime.time: DateTimeColumn,
        datetime.datetime: DateTimeColumn,
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
        # --- documents ------------------------------------------------------
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
        # --- arrays ----------------------------------------------------------
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
        # operator, and belongs to Phase 2b, so it is narrowed by name rather
        # than rendered as something weaker.
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

    #: The JSON **quantifier** operators. ``@>`` / ``@?`` are PostgreSQL's
    #: ``jsonb`` spellings and are absent as syntax here; ``any_of`` is the
    #: ``v = ANY(x)`` form, measured a syntax error on 2019 / 2022 / 2025.
    #: Narrowed by name so the answer exists before core grows the accessor,
    #: rather than appearing afterwards as an unexamined default.
    _JSON_QUANTIFIER_OPERATIONS = frozenset({"@>", "@?", "any_of"})

    #: Operations on ``JSONColumn`` that need SQL Server's JSON **function**
    #: family -- ``JSON_VALUE`` / ``JSON_QUERY`` / ``OPENJSON`` / ``ISJSON`` --
    #: and so are unavailable on a server older than 2016, which is where they
    #: all arrived. The boundary is :data:`SQL_SERVER_2016`, the same number
    #: :meth:`~...json.SQLServerJSONMixin.supports_json_type` uses, so the
    #: column-level answer and the expression-level one cannot drift.
    _JSON_FUNCTION_OPERATIONS = frozenset(
        {
            "json_path",
            "json_value",
            "array_length",
            "has_key",
            "json_valid",
            "array_contains",
            "unnest",
        }
    )

    def supports_column_operation(self, column_name: str, op: str) -> bool:
        """Whether ``op`` works on ``column_name`` on this server, at this version.

        Everything core's operation set offers is available except the pairs
        measured to fail. The narrowing is at the ``(column class, operation)``
        grain because that is the grain of the question: SQL Server cannot
        ``ilike`` a string, but it can still ``+`` two integers, and answering
        at the operation level alone would over-refuse every other column.

        The pairs, each with the measurement behind it:

        ``("StringColumn", "ilike")`` -- **always False**
            SQL Server has no ``ILIKE`` operator on any version. Measured on
            2019, 2022 and 2025, all three fail to parse, and the failure is
            unusual enough to be worth quoting: the parser takes ``ILIKE`` for a
            table alias and then complains **"An expression of non-boolean type
            ..."** where the pattern belongs
            (``suggested-pairing-string-enum.md`` §"发现" item 1, which also
            records that only PostgreSQL and ClickHouse have the operator at
            all). This is a narrowing rather than a capability loss, because
            SQL Server's default collation is already case-insensitive -- the
            same sweep measured storing ``'Zebra'`` and querying ``'zebra'``
            hitting one row on 2019, 2022 and 2025 alike -- so ``like`` stays
            available and is *not* narrowed. The portable case-insensitive
            spellings (``UPPER(col) LIKE UPPER(:pat)``, or the default
            collation itself) are a Phase 2b rendering decision.

        ``("JSONColumn", "@>" / "@?" / "any_of")`` -- **always False**
            The JSON quantifiers. ``@>`` and ``@?`` are PostgreSQL's ``jsonb``
            containment and key-existence operators and are not syntax here;
            ``any_of`` is the ``v = ANY(x)`` array quantifier, measured a
            **syntax error** on 2019, 2022 and 2025. Equivalent shapes exist
            under other names (``OPENJSON`` + ``EXISTS`` for containment,
            ``IN (SELECT CAST([value] AS INT) FROM OPENJSON)`` for the
            quantifier), but they are emulations rather than the operator, and
            an emulation that only *looks* like the operator is exactly the
            silent substitution the protocol forbids -- so the names are
            refused and the emulation is Phase 2b's to write deliberately.

        ``("JSONColumn", "json_path" / "json_value" / "array_length" /
        "has_key" / "json_valid" / "array_contains" / "unnest")`` -- **False
        below 2016**
            Every one of them needs the JSON function family, which arrived
            with 2016; an older server has no ``JSON_VALUE``, no ``OPENJSON``
            and no ``ISJSON`` at all. The gate is read from the same
            :data:`SQL_SERVER_2016` boundary :meth:`SQLServerJSONMixin.supports_json_type`
            uses rather than repeated, for the same reason the table's cells are
            cited: one number, two readers, so they cannot drift.

        Declared **available**, with the reason, because each of these is a trap
        a reader of this table would otherwise assume away:

        ``("JSONColumn", "json_equal" / "eq")``
            The column is text, so whole-column equality is available on every
            version -- and that is also why the *semantic* recipe matters:
            ``suggested-pairing-array.md`` §"发现" item 4a records that a plain
            text comparison is correct here (SQL Server does not normalise the
            way MySQL 5.7/8.0's ``JSON`` column does), while item 4b records
            that the shape is not portable. The obligation is on the renderer,
            not a missing capability.

        ``("UUIDColumn", ordering)``
            ``ORDER BY`` on ``uniqueidentifier`` works and is **not** the
            canonical text order on any version -- measured ``[2, 1, 3]`` where
            the text order is ``[1, 2, 3]``, with ``CONVERT(varchar(36), u)``
            restoring it. A rendering fact (Phase 2b), so narrowing it would
            refuse a query that runs.

        ``("StringColumn", "length")``
            ``LEN`` counts **UTF-16 code units** -- 5 for ``'中文abc'`` where
            ``DATALENGTH`` reports the 10 bytes
            (``suggested-pairing-string-enum.md`` §A, the sqlserver row; §8.4
            lists SQL Server as the UTF-16-code-unit member). A unit fact for
            the renderer, not a missing operation.

        Args:
            column_name: The column class name, as ``type(column).__name__`` --
                ``"StringColumn"``, ``"JSONColumn"``.
            op: The operation name, as the public method that provides it --
                ``"ilike"``, i.e.
                :meth:`StringPatternPredicateMixin.ilike
                <rhosocial.activerecord.backend.expression.mixins.StringPatternPredicateMixin.ilike>`.

        Returns:
            False where this dialect narrows, True everywhere else -- which
            includes every operation on every class not mentioned above, and
            every operation on an unadapted dialect except the JSON family
            (whose gate answers without a version; see
            :meth:`_has_json_functions`).
        """
        if column_name == StringColumn.__name__ and op == "ilike":
            return False

        if column_name == JSONColumn.__name__:
            if op in self._JSON_QUANTIFIER_OPERATIONS:
                return False
            if op in self._JSON_FUNCTION_OPERATIONS:
                return self._has_json_functions()

        return super().supports_column_operation(column_name, op)

    def _has_json_functions(self) -> bool:
        """Whether this server has SQL Server's JSON function family.

        2016 and later (:data:`SQL_SERVER_2016`), the same boundary
        :meth:`SQLServerJSONMixin.supports_json_type` declares.

        An unadapted dialect -- one built without a version, whose ``.version``
        property raises rather than answering -- is read as **before** 2016
        instead of raising, and for the same reason every other unadapted
        answer in this backend is: the refusal is the side that keeps a caller
        from being told a query will run when it will not. Reaching the version
        through ``_version`` is what makes that possible, since the property
        refuses to answer at all.
        """
        version = getattr(self, "_version", None)
        if version is None:
            return False
        return tuple(version) >= SQL_SERVER_2016


__all__ = ["SQLServerColumnSuggestionMixin", "COLUMN_TYPE_ENTRIES"]
