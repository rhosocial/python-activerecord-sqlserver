# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/types.py
"""SQL Server DataType formatting mixin."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.types import (
        SQLServerNCharType,
        SQLServerNVarCharType,
        SQLServerUniqueIdentifierType,
        SQLServerVarBinaryType,
        SQLServerXmlType,
    )

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    TimestampTzType,
    TinyIntType,
    VarCharType,
    XmlType,
)


class SQLServerTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):
    """SQL Server DataType formatting and parsing.

    Implements ``DDLTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DDLTypeMixin``). SQL Server-specific types carry ``sqlserver_``-prefixed
    names; core types render their real SQL Server SQL.

    Spellings
    ---------
    A concept with several spellings (``INTEGER``/``INT``, ``DECIMAL``/
    ``NUMERIC``/``DEC``) declares them as a closed ``SPELLINGS`` list and the
    formatter states which of them this backend renders through
    ``_check_spelling``.  T-SQL writes none of the alternatives below, so every
    spelling of every concept is accepted and normalised to the T-SQL word —
    refusing one would refuse the concept's own default spelling, which is the
    spelling every plainly-constructed type carries.  The gate is still called
    on every such formatter, because the *only* way an unknown spelling can be
    rejected rather than interpolated into SQL is for it to be checked against
    the closed list.

    Signedness
    ----------
    ``unsigned`` is in the integer concepts' ``PARAMETERS``, so it is part of
    their identity: ``IntegerType(unsigned=True)`` is a different column from
    ``IntegerType()`` and the differ compares them as such.  A formatter may
    therefore honour it or refuse it, and there is no third option — T-SQL has
    no unsigned integer wider than one byte and no ``UNSIGNED`` attribute, so
    every integer formatter here refuses it.  See
    :meth:`_refuse_unsigned_integer`, and :meth:`_refuse_unsigned_tinyint` for
    the one width whose refusal is about a different reason.

    The same rule governs every other identity field, and the rule is not
    satisfied by writing the type word and moving on.  Two of this backend's
    fields are refused rather than honoured, for two different reasons:

    * ``unsigned`` — there is no T-SQL column it could name.
    * ``DecimalType.scale`` with no ``precision`` — there *is* a T-SQL column it
      could name, but T-SQL's grammar does not let the scale be named on its
      own: ``decimal[(p[,s])]``, and the reference says a scale "can only be
      specified if precision is specified".  So the request has no spelling at
      all on this backend, which is the same failure as the first and needs the
      same answer.  See :meth:`format_data_type_decimal`.

    A third thing is neither honoured nor unexpressible: a *number* outside the
    range T-SQL documents.  ``DECIMAL(p, s)`` with ``s < 0`` and ``VARCHAR(n)``
    with ``n`` above 8000 are declarations this grammar has no trouble writing
    and the server no trouble rejecting, so they are answered with
    ``ValueError`` — which names the offending value and the documented bound —
    rather than with ``UnsupportedFeatureError``, which is reserved for a
    declaration the grammar cannot express at all.  See
    :meth:`_check_decimal_scale_sign` and :meth:`_check_length`.

    Everything else this dialect models is honoured: ``DECIMAL(p, s)``,
    ``FLOAT(p)``, ``DATETIME2(p)``, ``TIME(p)`` and ``DATETIMEOFFSET(p)`` all
    take the parameter they are given and render it, which is what makes two
    declarations that differ in one a different column in the DDL as well as in
    ``identity()``.
    """

    # ------------------------------------------------------------------
    # What this dialect supplies for a width left undeclared
    # ------------------------------------------------------------------

    #: The widths T-SQL gives a character or byte column whose ``n`` was not
    #: written, keyed by concept name — the ``format_data_type_<name>`` dispatch
    #: key, so a backend type declares under its own name.
    #:
    #: **Every value here was read off a live server, and one of them is not
    #: T-SQL's own default.**  A bare declaration was created and the catalog
    #: read back, identically on SQL Server 2022 (16.0.4250.1) and 2025
    #: (17.0.4035.5), which agree on all of it::
    #:
    #:     CREATE TABLE #probe (v VARCHAR, c CHAR, nv NVARCHAR, nc NCHAR)
    #:     -- sys.columns.max_length -> 1, 1, 2, 2
    #:
    #: ``max_length`` is in bytes and ``nvarchar`` counts byte-pairs, so those
    #: four are lengths of **1** each.  For what the vendor says as well as
    #: what the server did: the reference documents ``n`` for ``varchar(n)`` as
    #: "a value from 1 through 8,000", and its sentence about an unspecified
    #: ``n`` giving a length of 1 is scoped to variable and parameter
    #: declarations.  **A column definition's own default is not spelled out on
    #: that page**, which is why the measurement above is quoted rather than a
    #: paraphrase: it is the only thing here that answers the question actually
    #: being asked.
    #: https://learn.microsoft.com/en-us/sql/t-sql/data-types/char-and-varchar-transact-sql
    #:
    #: So:
    #:
    #: * ``char``, ``sqlserver_nchar`` — **1, and the measured server default.**
    #:   The declaration and the server agree, so nothing is being asserted
    #:   against the vendor here.
    #: * ``varchar``, ``sqlserver_nvarchar`` — **255, which is *not* T-SQL's
    #:   default.**  This dialect has always written 255 for an undeclared
    #:   width, and 1 would silently truncate every name, address and slug
    #:   written through a bare ``VarCharType`` — the server would accept the
    #:   DDL and store one character.  255 is therefore a decision of *this*
    #:   backend, stated here rather than implied, and the reason it is a
    #:   decision is the vendor sentence above: the server's own 1 is the one
    #:   number that must not be adopted by accident.
    #:
    #: What this buys is that the two numbers the schema differ compares are one
    #: value instead of two.  A bare ``VarCharType`` used to render
    #: ``VARCHAR(255)`` while carrying no length, so the declared type and the
    #: catalog's report of the very column it produced compared **unequal** and
    #: the differ invented a change on every undeclared string column.
    #:
    #: ``sqlserver_nvarchar_max`` is **absent on purpose**: ``NVARCHAR(MAX)`` is
    #: unbounded because ``MAX`` lifted a cap, which is a different statement
    #: from "no width was declared", and it is carried by its own class for
    #: exactly that reason.  Nothing exempts it — an absent entry *is* the
    #: declaration that this concept's bare form has no width.
    def type_parameter_defaults(self) -> dict:
        return {
            "char": {"length": 1},
            "varchar": {"length": 255},
            "sqlserver_nchar": {"length": 1},
            "sqlserver_nvarchar": {"length": 255},
        }

    # --- SQL Server-specific type formatters (dispatch key = type name) ---

    def format_data_type_sqlserver_nvarchar(self, data_type: "SQLServerNVarCharType") -> Tuple[str, tuple]:
        """``NVARCHAR(n)``, with ``n`` bounded as T-SQL documents it.

        ``n`` counts byte-pairs here, not bytes, which is why the documented
        ceiling is 4000 rather than the 8000 of ``VARCHAR(n)``; a declared length
        outside the documented range is refused rather than truncated, and
        :meth:`_check_length` writes the range out and says why this backend
        checks the intersection of the page's two statements about the lower
        bound.  Declaring no length is this dialect's ``NVARCHAR(255)`` — which
        T-SQL does **not** do; see :meth:`type_parameter_defaults`, where the
        measured value and the reason this backend differs from it are written
        down.  A type that carries no length still renders the declared width,
        because the fallback here and the declaration there are the same number
        and neither may drift from the other.
        """
        self._check_length("NVARCHAR", data_type.length)
        return (f"NVARCHAR({data_type.length})" if data_type.length is not None else "NVARCHAR(255)"), ()

    def format_data_type_sqlserver_nchar(self, data_type: "SQLServerNCharType") -> Tuple[str, tuple]:
        """``NCHAR(n)``, with ``n`` bounded as T-SQL documents it.

        Same 4000 ceiling as :meth:`format_data_type_sqlserver_nvarchar` and the
        same intersection rule; see :meth:`_check_length`.  A shorter value is
        blank-padded to ``n``, which is what makes this concept fixed-length
        rather than variable-length.  Declaring no length is this dialect's
        ``NCHAR(1)``, and here that is also the measured server default — a bare
        ``NCHAR`` reports ``max_length = 2`` bytes on SQL Server 2022 and 2025,
        which is one byte-pair; see :meth:`type_parameter_defaults`.
        """
        self._check_length("NCHAR", data_type.length)
        return (f"NCHAR({data_type.length})" if data_type.length is not None else "NCHAR(1)"), ()

    def format_data_type_sqlserver_nvarchar_max(self, data_type) -> Tuple[str, tuple]:
        return "NVARCHAR(MAX)", ()

    def format_data_type_sqlserver_varbinary(self, data_type: "SQLServerVarBinaryType") -> Tuple[str, tuple]:
        """``VARBINARY(n)``, with ``n`` bounded as T-SQL documents it.

        T-SQL documents ``varbinary(n)`` as "n can be a value from 1 through
        8,000", and its Remarks separately that "The data that is entered can be
        0 bytes in length" — a statement about the *value*, which is how an empty
        byte string is written, not a way to declare ``n = 0``.  So the whole
        documented range is enforced here, unlike the two character families
        where one page states two different lower bounds; see
        :meth:`_check_length`.  ``VARBINARY(MAX)`` is the unbounded spelling and
        is a class of its own.
        """
        self._check_length("VARBINARY", data_type.length)
        if data_type.length is not None:
            return f"VARBINARY({data_type.length})", ()
        return "VARBINARY(255)", ()

    def format_data_type_sqlserver_varbinary_max(self, data_type) -> Tuple[str, tuple]:
        return "VARBINARY(MAX)", ()

    def format_data_type_sqlserver_xml(self, data_type: "SQLServerXmlType") -> Tuple[str, tuple]:
        """SQL Server's own ``xml`` spelling.

        SQL Server has a native ``xml`` type, so the XML concept is *rendered*
        here rather than substituted with text.  It is not text either: the
        storage is a binary representation (see ``SQLServerXmlType``).
        """
        return "XML", ()

    def format_data_type_sqlserver_tinyint(self, data_type) -> Tuple[str, tuple]:
        """SQL Server ``TINYINT``, unsigned, for either spelling.

        No ``UNSIGNED`` modifier is emitted: T-SQL's ``TINYINT`` *is* unsigned
        and has no signed spelling, so the ``unsigned`` field on the type class
        records the fact rather than the DDL spelling it.  ``INT1`` is not a
        T-SQL word but names the same 8-bit concept, so it renders as
        ``TINYINT`` rather than being refused.

        There is nothing to refuse here, and that is worth stating: this class
        pins ``unsigned=True`` in its own ``__init__`` and takes no flag, so
        this formatter cannot be reached with ``unsigned=False``.  The signedness
        gate lives on the *generic* concept instead — see
        :meth:`_refuse_unsigned_tinyint`, which is where a caller who writes
        ``TinyIntType(unsigned=True)`` is sent here by name.
        """
        self._check_spelling(data_type, TinyIntType)
        return "TINYINT", ()

    def format_data_type_sqlserver_bit(self, data_type) -> Tuple[str, tuple]:
        """SQL Server ``BIT`` — the boolean, not a bit string.

        Unlike MySQL's and PostgreSQL's ``BIT(n)``, T-SQL's ``BIT`` takes no
        length and holds ``0`` / ``1`` / ``NULL``; see ``SQLServerBitType``.
        """
        return "BIT", ()

    def format_data_type_sqlserver_image(self, data_type) -> Tuple[str, tuple]:
        return "IMAGE", ()

    def format_data_type_sqlserver_uniqueidentifier(
        self, data_type: "SQLServerUniqueIdentifierType"
    ) -> Tuple[str, tuple]:
        return "UNIQUEIDENTIFIER", ()

    # --- Core types (pure names) rendered to real SQL Server SQL ---

    #: The documented range of each signed T-SQL integer width, written as the
    #: reference writes it.  Quoted in the refusal below so the caller reads the
    #: column it would otherwise have got.  The ``_SQLSERVER_`` prefix is what
    #: ``_register_type_formatters()`` copies onto the dialect class alongside
    #: the formatters that read it: inside a copied formatter ``self`` is the
    #: dialect, not this mixin.
    #: https://learn.microsoft.com/en-us/sql/t-sql/data-types/int-bigint-smallint-and-tinyint-transact-sql
    _SQLSERVER_INTEGER_RANGES = {
        "INT": "-2,147,483,648 to 2,147,483,647",
        "SMALLINT": "-32,768 to 32,767",
        "BIGINT": (
            "-9,223,372,036,854,775,808 to 9,223,372,036,854,775,807"
        ),
    }

    def _refuse_unsigned_integer(self, data_type, word: str) -> None:
        """Refuse ``unsigned=True``, because T-SQL has no unsigned integer of
        any width above one byte and no ``UNSIGNED`` attribute to write.

        The core integer concepts carry signedness as a field rather than as a
        class, so ``IntegerType(unsigned=True)`` is constructible and the flag
        reaches the formatter.  It is also in ``PARAMETERS``, hence in
        ``__eq__``/``__hash__``, hence two declarations differing only in it are
        different columns — so the flag has to change the rendered SQL or stop
        the render.  Writing the signed column and reporting success is the
        second thing: the column then accepts the negatives the caller declared
        it would not, and nothing says so.

        What the documentation says, which is why the answer is a refusal:

        * The integer types are enumerated as ``bigint``, ``int``, ``smallint``
          and ``tinyint`` under "Exact numerics", and the four of them are
          documented with one symmetric range each — ``bigint`` -2^63 to
          2^63-1, ``int`` -2^31 to 2^31-1, ``smallint`` -2^15 to 2^15-1 — and
          no unsigned counterpart for any of them.  The exact-numeric category
          is closed: ``tinyint``, ``smallint``, ``int``, ``bigint``, ``bit``,
          ``decimal``, ``numeric``, ``money``, ``smallmoney``.  There is no
          unsigned row to select.
          https://learn.microsoft.com/en-us/sql/t-sql/data-types/data-types-transact-sql
          https://learn.microsoft.com/en-us/sql/t-sql/data-types/int-bigint-smallint-and-tinyint-transact-sql
        * There is not even a spelling that would parse.  ``<column_definition>``
          is ``column_name <data_type>`` followed by ``FILESTREAM``,
          ``COLLATE``, ``SPARSE``, ``MASKED``, ``DEFAULT``, ``IDENTITY``,
          ``GENERATED ALWAYS AS``, nullability, ``ROWGUIDCOL`` and
          ``ENCRYPTED WITH`` — no type modifier, and no ``UNSIGNED`` or
          ``SIGNED`` token anywhere in the statement reference.
          https://learn.microsoft.com/en-us/sql/t-sql/statements/create-table-transact-sql
        * Two nearby things are *not* signedness, and are named here so the
          next reader does not mistake them for it.  ``IDENTITY[(seed,
          increment)]`` is the auto-numbering property, assignable to
          ``tinyint``, ``smallint``, ``int``, ``bigint``, ``decimal(p,0)`` and
          ``numeric(p,0)`` alike — a signed and an unsigned request alike get
          the same counter.  And ``sql_variant`` is a column that stores a
          *base type* per value ("a data type that stores values of various
          SQL Server-supported data types", with ``SQL_VARIANT_PROPERTY``
          reporting ``BaseType``); the base types it can hold are the signed
          integers above, so it widens a column's type vocabulary without
          adding a signedness to any of them.
          https://learn.microsoft.com/en-us/sql/t-sql/data-types/sql-variant-transact-sql

        The signed range does cover each width's unsigned range, so nothing is
        lost by dropping the *concept* here; what would be lost is the caller's
        statement that this particular column holds no negative value, and that
        belongs in a ``CHECK`` constraint.
        """
        if not data_type.unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"an unsigned {word} column "
            f"(SQL Server has no unsigned integer type; {word} is a signed "
            f"integer documented as {self._SQLSERVER_INTEGER_RANGES[word]}, "
            f"and T-SQL has no UNSIGNED attribute to write after the type name)",
            suggestion=(
                "Declare the column signed and enforce the range with a CHECK "
                "constraint if negatives must be rejected."
            ),
        )

    def _refuse_unsigned_numeric(self, data_type, word: str) -> None:
        """Refuse ``unsigned=True`` on ``DECIMAL``, ``FLOAT``, ``REAL`` or
        ``DOUBLE``.

        The same field reaches these four concepts that it reaches the integer
        widths -- ``DecimalType``, ``FloatType``, ``RealType`` and
        ``DoubleType`` each carry ``unsigned`` in ``PARAMETERS``, so two
        declarations differing only in it are different columns as far as the
        schema differ is concerned -- and T-SQL's answer is a refusal, for its
        own reasons.

        Note first what this is **not**.  ``_refuse_unsigned_tinyint`` refuses
        the flag on one width because T-SQL *has* that unsigned column and the
        class that owns it already exists.  There is no such case here: no T-SQL
        numeric column is unsigned, so there is no second declaration to move the
        request to, and no ``SQLServer*Type`` to name instead.

        What the documentation says:

        * **The categories are closed and carry no unsigned row.**
          ``decimal`` and ``numeric`` are in "Exact Numerics", documented with
          that category as ``tinyint``, ``smallint``, ``int``, ``bigint``,
          ``bit``, ``decimal``, ``numeric``, ``money``, ``smallmoney``;
          ``float`` and ``real`` are the whole of "Approximate Numerics".
          https://learn.microsoft.com/en-us/sql/t-sql/data-types/data-types-transact-sql
        * **Their documented ranges are signed on both sides.**  The reference
          gives ``float`` as "- 1.79E+308 to -2.23E-308, 0 and 2.23E-308 to
          1.79E+308" and ``real`` as "- 3.40E + 38 to -1.18E - 38, 0 and 1.18E -
          38 to 3.40E + 38", and says of both: "The behavior of float and real
          follows the IEEE 754 specification on approximate numeric data types"
          -- and IEEE 754 binary formats carry a signed exponent in their field
          layout, so there is no unsigned binary format for a column to be.
          https://learn.microsoft.com/en-us/sql/t-sql/data-types/float-and-real-transact-sql
          ``decimal``/``numeric`` are exact numeric with a maximum precision of
          38, which is a bound on the digits a column holds rather than a
          signedness.
          https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql
        * **There is not even a spelling that would parse.**
          ``<column_definition>`` is ``column_name <data_type>`` followed by
          ``FILESTREAM``, ``COLLATE``, ``SPARSE``, ``MASKED``, ``DEFAULT``,
          ``IDENTITY``, ``GENERATED ALWAYS AS``, nullability, ``ROWGUIDCOL``
          and ``ENCRYPTED WITH`` -- no type modifier, and no ``UNSIGNED`` or
          ``SIGNED`` token anywhere in the statement reference.
          https://learn.microsoft.com/en-us/sql/t-sql/statements/create-table-transact-sql

        Writing a bare ``DECIMAL`` or ``FLOAT(53)`` for an unsigned request would
        create a column that accepts the negatives the caller declared it would
        not, and report success: the same silent loss as accepting the flag and
        discarding it, which is what this replaces.

        ``word`` is the word T-SQL writes -- ``DOUBLE PRECISION`` is rendered
        ``FLOAT(53)`` and ``DECIMAL`` keeps its own spelling -- so the message
        names the request and the rendering together.

        ``UnsupportedFeatureError``, not ``ValueError``: this is a declaration
        the grammar cannot express at all rather than a wrong value, and the two
        exceptions do not share a base class.
        """
        if not data_type.unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"an unsigned {word} column "
            f"(SQL Server has no unsigned floating-point or fixed-point type: "
            f"decimal and numeric are Exact Numerics and float and real are the "
            f"whole of Approximate Numerics, neither category has an unsigned "
            f"row, float's documented range is -1.79E+308 to -2.23E-308, 0 and "
            f"2.23E-308 to 1.79E+308 and real's is -3.40E+38 to -1.18E-38, 0 and "
            f"1.18E-38 to 3.40E+38, float and real follow the IEEE 754 "
            f"specification whose binary formats have a signed exponent, and "
            f"T-SQL's column grammar has no type modifier position after the "
            f"type name, so there is not even a spelling that would parse)",
            suggestion=(
                "Declare the column signed and enforce the range with a CHECK "
                "constraint if negatives must be rejected."
            ),
        )

    def _refuse_unsigned_tinyint(self, data_type) -> None:
        """Refuse ``unsigned=True`` on the *generic* 8-bit concept, for a
        reason that is not the one above: T-SQL **does** have an unsigned
        integer, and it is exactly this width.

        ``TINYINT`` is documented as "0 to 255", range expression
        ``2^0-1 to 2^8-1``, one byte — unsigned, with no signed 8-bit integer
        beside it in the exact-numeric list.
        https://learn.microsoft.com/en-us/sql/t-sql/data-types/int-bigint-smallint-and-tinyint-transact-sql

        So there is no second T-SQL word for the flag to switch to: the
        rendering for ``unsigned=True`` and for ``unsigned=False`` would be the
        same ``TINYINT`` column, which is precisely the paradigm violation —
        and the unsigned column it would produce is already declared by
        :class:`SQLServerTinyIntType`, which pins ``unsigned=True`` in its own
        ``__init__`` and renders that same ``TINYINT``.  Honouring the flag
        here would give the caller two declarations for one column that a
        differ could not tell apart by their SQL, so it is refused and the class
        that owns the column is named instead.

        What the flag cannot express on this width is the other direction
        either, and that is stated rather than papered over: T-SQL has no
        signed 8-bit integer, so a *signed* ``TinyIntType`` also renders
        ``TINYINT``, an unsigned column.  That is the signedness collapse this
        backend performs, in the same place SQLite collapses every integer
        width to ``INTEGER`` — the vendor fixes the range of the only 8-bit
        type, and the width a caller can have is whatever T-SQL offers.  A
        value that must be allowed to go negative needs ``SMALLINT``, the
        narrowest signed width T-SQL has.
        """
        if not data_type.unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            "an unsigned TINYINT column declared on the generic TinyIntType "
            "(T-SQL's only 8-bit integer, TINYINT, is itself unsigned - "
            "documented as 0 to 255 with no signed spelling - so there is no "
            "second T-SQL word for this flag to change the rendering to, and "
            "the unsigned 8-bit column is already declared by "
            "SQLServerTinyIntType, which pins unsigned=True)",
            suggestion=(
                "Declare SQLServerTinyIntType, which is this backend's unsigned "
                "8-bit integer and renders TINYINT; a column that must also "
                "hold negatives needs SMALLINT, the narrowest signed width T-SQL "
                "has."
            ),
        )

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        """``INT`` for both spellings.

        T-SQL accepts ``INT`` and ``INTEGER`` interchangeably for the same
        signed 32-bit integer and reports ``int`` from the catalog, so the
        spelling is normalised to ``INT`` — T-SQL's own word — rather than
        refused.  ``INT4`` is not accepted: it is not in the concept's closed
        spelling list, and accepting words T-SQL never writes would make the
        list meaningless.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`, which is also where the reason for
        the refusal is written down.
        """
        self._check_spelling(data_type, IntegerType)
        self._refuse_unsigned_integer(data_type, "INT")
        return "INT", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        """``BIGINT`` for both spellings; T-SQL has no ``INT8`` of its own but
        both name the same signed 64-bit integer, so neither is refused.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`."""
        self._check_spelling(data_type, BigIntType)
        self._refuse_unsigned_integer(data_type, "BIGINT")
        return "BIGINT", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        """``SMALLINT`` for both spellings, for the same reason as
        :meth:`format_data_type_bigint`.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`."""
        self._check_spelling(data_type, SmallIntType)
        self._refuse_unsigned_integer(data_type, "SMALLINT")
        return "SMALLINT", ()

    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        """``TINYINT`` for both spellings.

        This is the concept class; the unsigned 8-bit backend class is
        :class:`SQLServerTinyIntType`.  Both render ``TINYINT`` because T-SQL
        has no signed 8-bit integer to distinguish: the range of the only
        8-bit type is fixed by the vendor, so the ``unsigned`` field records a
        property of the type rather than a word to write.

        ``unsigned`` is refused rather than ignored — but not because T-SQL has
        no unsigned integer, which is the argument on
        :meth:`_refuse_unsigned_integer`.  It is refused because ``TINYINT``
        *is* that unsigned integer and :class:`SQLServerTinyIntType` already
        declares it; see :meth:`_refuse_unsigned_tinyint`, which is where that
        reasoning is written down and where the class to use instead is named.
        """
        self._check_spelling(data_type, TinyIntType)
        self._refuse_unsigned_tinyint(data_type)
        return "TINYINT", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        """``FLOAT(p)`` for a declared precision, bare ``FLOAT`` for none.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`, which is also where the reason is
        written down.  It is checked first so an unsigned request is answered the
        same way whether or not it also named a precision, and the precision's own
        ``ValueError`` is untouched for a signed declaration.
        """
        self._refuse_unsigned_numeric(data_type, "FLOAT")
        if data_type.precision is not None:
            if not (1 <= data_type.precision <= 53):
                raise ValueError(
                    f"SQL Server FLOAT precision must be 1-53, "
                    f"got {data_type.precision}"
                )
            return f"FLOAT({data_type.precision})", ()
        return "FLOAT", ()

    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        """``REAL``, and ``unsigned`` refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`.

        Worth being precise about what this refusal is *not*, because the
        briefing for this field described it wrongly and the distinction is the
        whole reason the message says what it says.  T-SQL ``real`` is **not**
        ``FLOAT(53)``: ``REAL`` is its own row in "Approximate Numerics", a
        4-byte single-precision type with its own documented range -- "- 3.40E +
        38 to -1.18E - 38, 0 and 1.18E - 38 to 3.40E + 38" -- while 8-byte double
        precision is separately rendered ``FLOAT(53)`` by
        :meth:`format_data_type_double`.  So this formatter drops the field on a
        concept whose storage really is that concept, not on one standing in for
        another.  ``REAL`` is one of the two words T-SQL writes verbatim, so
        nothing about a *signed* declaration moves.
        https://learn.microsoft.com/en-us/sql/t-sql/data-types/float-and-real-transact-sql

        The signedness is still refused, for the reasons in
        :meth:`_refuse_unsigned_numeric`: that range is signed on both sides,
        the reference says "The behavior of float and real follows the IEEE 754
        specification", IEEE 754 binary formats carry a signed exponent in their
        field layout, and T-SQL's ``<column_definition>`` has no type-modifier
        position after the type name in which ``UNSIGNED`` could go.
        """
        self._refuse_unsigned_numeric(data_type, "REAL")
        return "REAL", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        """``FLOAT(53)`` for both spellings.

        T-SQL has no ``DOUBLE``: 8-byte floating point *is* ``FLOAT(53)``, the
        form the server itself reports for a ``double precision`` column, so
        that is what a requested double precision renders as -- Microsoft says so
        in its own words: "The synonym for **double precision** is
        **float(53)**".
        https://learn.microsoft.com/en-us/sql/t-sql/data-types/float-and-real-transact-sql

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`.  ``FLOAT(53)``'s documented range is
        "- 1.79E+308 to -2.23E-308, 0 and 2.23E-308 to 1.79E+308" -- signed on
        both sides -- so there is no unsigned double-precision column on this
        server for the request to have become.
        """
        self._check_spelling(data_type, DoubleType)
        self._refuse_unsigned_numeric(data_type, "DOUBLE PRECISION")
        return "FLOAT(53)", ()

    def _check_decimal_scale_sign(self, data_type: DecimalType) -> None:
        """Refuse a negative ``scale``, which T-SQL's documented range excludes.

        The one sentence that fixes the bound is the reference's own, in its
        ``s`` (scale) entry: "Scale must be a value from 0 through *p*, and can
        only be specified if precision is specified.  The default scale is 0,
        and so 0 <= s <= p."
        https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql

        So ``0 <= s`` is the lower half of that bound, and it holds for *every*
        precision: the smallest documented precision is 1, so no ``p`` makes a
        negative ``s`` legal.  That is why this is checked before the
        un-anchorable-scale refusal rather than folded into it — a negative scale
        is wrong whatever precision it is declared with, and a refusal that said
        "name the precision too" would be advice that does not work.

        The ``scale <= precision`` comparison further down cannot see this, which
        is how ``DECIMAL(10, -1)`` reached the DDL: ``-1`` is not greater than
        ``10``, so the check passed and the server rejected the statement.
        ``DECIMAL(5, -1)`` and a bare ``DecimalType(scale=-1)`` were the same
        story.

        Nothing is clamped to 0.  A negative scale is not a small scale, and
        rounding it up would hand the caller a column other than the one they
        declared — the same defect as dropping the value.

        ``ValueError``, and not ``UnsupportedFeatureError``: ``DECIMAL(p, s)`` is
        a declaration this grammar expresses perfectly well, so nothing is
        inexpressible here; the number is simply outside the documented range.
        The two exceptions do not share a base class, which is why the project's
        cross-backend rule keeps them apart.
        """
        if data_type.scale is None or data_type.scale >= 0:
            return
        raise ValueError(
            f"SQL Server DECIMAL scale must not be negative, got "
            f"{data_type.scale} (T-SQL's reference says 'Scale must be a value "
            f"from 0 through p, and can only be specified if precision is "
            f"specified. The default scale is 0, and so 0 <= s <= p.' - the "
            f"lower bound holds for every precision, since the smallest "
            f"documented precision is 1, so no precision makes a negative scale "
            f"legal)"
        )

    #: T-SQL's documented inline length bounds, as ``word -> (smallest,
    #: largest)``.  ``n`` is bytes for ``CHAR`` / ``VARCHAR`` / ``BINARY`` /
    #: ``VARBINARY`` ("1 through 8,000") and byte-pairs for ``NCHAR`` /
    #: ``NVARCHAR`` ("1 through 4,000"), which is why the national pair has the
    #: lower ceiling.  The lower bounds differ between the two families for a
    #: reason that is about the *documentation*, not about T-SQL, and
    #: :meth:`_check_length` sets it out.
    #: https://learn.microsoft.com/en-us/sql/t-sql/data-types/char-and-varchar-transact-sql
    #: https://learn.microsoft.com/en-us/sql/t-sql/data-types/binary-and-varbinary-transact-sql
    #: https://learn.microsoft.com/en-us/sql/t-sql/data-types/nchar-and-nvarchar-transact-sql
    _SQLSERVER_LENGTH_LIMITS = {
        "CHAR": (0, 8000),
        "VARCHAR": (0, 8000),
        "NCHAR": (0, 4000),
        "NVARCHAR": (0, 4000),
        "VARBINARY": (1, 8000),
    }

    def _check_length(self, word: str, length) -> None:
        """Refuse a declared length outside T-SQL's documented inline range.

        The bound checked here is the **intersection** of every range the
        vendor's page states for that ``word`` — the largest lower bound and the
        smallest upper bound any documented sentence gives — because a value
        outside the intersection is one no documented reading of T-SQL permits,
        while a value inside it may still be one some reading excludes.  Nothing
        else is defensible without a server to ask, and this backend has none.

        What each page states, per family:

        * ``char(n)`` / ``varchar(n)`` — "must be a value from 1 through 8,000"
          in the Arguments, and "the n defines the string length in bytes (0 to
          8,000)" in the Remarks.  The ceiling agrees; the floor does not.
        * ``nchar(n)`` / ``nvarchar(n)`` — "must be a value from 1 through 4,000"
          and "byte-pairs (0-4,000)".  The same disagreement, at half the size.
        * ``binary(n)`` / ``varbinary(n)`` — "n is a value from 1 through 8,000"
          and "n can be a value from 1 through 8,000", and no second statement
          about ``n``: the Remarks' "The data that is entered can be 0 bytes in
          length" is about the *value*, not the parameter, and is not a way to
          declare ``n = 0``.  This is the one family with a single unambiguous
          range, and the only place the enforced floor is 1 rather than 0.

        That is the whole of the asymmetry in the table above, and it is worth
        writing out rather than resolving silently.  Refusing ``VARCHAR(0)`` would
        be enforcing one sentence against another on one page, so it is not
        refused; rendering ``VARCHAR(0)`` verbatim is at least faithful — the
        declaration the caller wrote is the declaration that reaches the DDL, and
        the check does not invent a bound the vendor has not stated.  A negative
        ``n`` is excluded by *both* readings of both character pages, so it is
        refused.

        Above the ceiling the pages agree, and so does the server: ``VARCHAR``
        over 8000 is the classic "The size of the data type varchar(n) exceeds
        the maximum allowed for any data type (8000)", and ``NVARCHAR(4001)`` is
        the same statement at half the size.  Those reached the DDL unchecked
        before.

        ``ValueError``, not ``UnsupportedFeatureError``: ``VARCHAR(n)`` is a
        declaration this grammar expresses perfectly well; the number is what is
        out of range.  Nothing is truncated to the ceiling — a clamped length is
        a column other than the one declared.
        """
        smallest, largest = self._SQLSERVER_LENGTH_LIMITS[word]
        if length is None or smallest <= length <= largest:
            return
        raise ValueError(
            f"SQL Server {word} length must be {smallest}-{largest}, got "
            f"{length} (T-SQL's own reference for {word} documents the inline "
            f"length n as a value from {smallest} through {largest}, and "
            f"declaring a length outside that is a statement the server "
            f"rejects; above the ceiling it is the well-known 'exceeds the "
            f"maximum allowed for any data type (8000)' error)"
        )

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        """``DECIMAL`` for all three spellings, and the two ways a scale or a
        precision can be wrong on this grammar.

        T-SQL's own documented interchangeability: ``DECIMAL``, ``NUMERIC`` and
        ``DEC`` are one type, and the catalog reports ``decimal``.

        **``scale`` without ``precision`` is refused**, and the reason is the
        vendor's own grammar rather than an argument borrowed from PostgreSQL.
        The documented syntax is ``decimal [ ( p [ , s ] ) ]`` and ``numeric [
        ( p [ , s ] ) ]`` — the scale is *inside* the precision's brackets, and
        the ``s`` entry says so in its own words: "Scale must be a value from 0
        through *p*, **and can only be specified if precision is specified**.  The
        default scale is 0, and so 0 <= s <= p."
        https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql

        That last clause settles it in T-SQL's terms rather than PostgreSQL's:
        there is no declaration in which a scale appears without a precision, so
        the alternative reading — "the scale, with T-SQL's default precision of
        18" — does not exist either, the same way it does not on PostgreSQL.
        That the two backends reach the same answer here is a coincidence of
        their grammar agreeing, not an inheritance: what is quoted above is
        Microsoft's sentence, and the checked ranges are this backend's.

        Writing bare ``DECIMAL`` instead would not be a small loss.  T-SQL's
        documented defaults are a precision of 18 and a scale of 0, so bare
        ``DECIMAL`` is ``DECIMAL(18, 0)``: eighteen digits, none of them
        fractional.  A request that named ``scale=2`` and nothing else asked for
        a fractional column and would have been handed one with none.  And the
        only other spelling that reaches a scale at all, ``DECIMAL(p)``, means
        scale 0 for the same reason.  Neither the precision nor the scale is this
        formatter's to invent, so the render stops and says which field is
        missing.

        **A negative scale is refused, with ``ValueError``**, and that is a
        different fault from the one above.  The same sentence that forbids a
        bare scale also fixes the range: "Scale must be a value from 0 through
        *p* ... and so 0 <= s <= p".  A negative ``s`` is below the lower bound
        for *every* possible ``p``, so no precision rescues it — telling the
        caller to add a precision would be advice that does not work.  The
        existing ``scale <= precision`` comparison cannot see it, because ``-1``
        is not greater than ``10``; ``DECIMAL(10, -1)`` used to render that way
        and the server rejected it.  Nothing is clamped to 0.

        The two exceptions are not interchangeable — they do not share a base
        class — so the distinction is kept: ``scale=2`` alone is a declaration
        this grammar cannot express (``UnsupportedFeatureError``, with a route
        forward), while ``scale=-1`` is a number outside the range this server
        accepts (``ValueError``, naming the value and the bound).

        What this is *not*: the scale is honoured, visibly, on every request
        that carries a precision.  ``DECIMAL(10, 2)`` and ``DECIMAL(10, 0)`` are
        different columns — T-SQL's own reference says "SQL Server considers each
        combination of precision and scale as a different data type" — and this
        dialect renders them differently, which is what keeps them different.
        Only the un-anchorable request and the out-of-range value are refused.

        ``unsigned`` is refused as well, and by the same method that refuses it
        for the two floating-point concepts; see :meth:`_refuse_unsigned_numeric`.
        It is checked **first**, before the spelling and the scale-sign checks
        below, and that ordering is deliberate: ``unsigned`` is the one of this
        class's identity fields that T-SQL's grammar cannot express at all, so it
        is answered the same way whether or not the request also named numbers
        this backend would have had to judge. Every check below is untouched and
        still fires for a signed declaration.
        """
        self._refuse_unsigned_numeric(data_type, "DECIMAL")
        self._check_spelling(data_type, DecimalType)
        self._check_decimal_scale_sign(data_type)
        if data_type.scale is not None and data_type.precision is None:
            raise UnsupportedFeatureError(
                self.name,
                f"a DECIMAL(p,s) column declared with scale={data_type.scale} "
                f"and no precision (T-SQL's grammar is decimal[(p[,s])]: the "
                f"scale is inside the precision's brackets and, in the "
                f"reference's words, 'can only be specified if precision is "
                f"specified' - so there is no DECIMAL declaration that carries a "
                f"scale alone, and no type modifier position after the type name "
                f"where one could go)",
                suggestion=(
                    f"Declare the precision as well: DECIMAL(p,s) renders "
                    f"DECIMAL(p, {data_type.scale}), and T-SQL requires 0 <= s "
                    f"<= p with a maximum precision of 38.  A bare DECIMAL is "
                    f"DECIMAL(18, 0) - a default precision of 18 and a default "
                    f"scale of 0 - so it is not the column a bare scale asked "
                    f"for, and DECIMAL(p) alone would mean scale 0."
                ),
            )
        if data_type.precision is not None:
            if not (1 <= data_type.precision <= 38):
                raise ValueError(
                    f"SQL Server DECIMAL precision must be 1-38, "
                    f"got {data_type.precision}"
                )
        if data_type.scale is not None:
            if data_type.precision is not None and data_type.scale > data_type.precision:
                raise ValueError(
                    f"SQL Server DECIMAL scale ({data_type.scale}) "
                    f"must not exceed precision ({data_type.precision})"
                )
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        """``BIT`` for both spellings — T-SQL's own name for the boolean."""
        self._check_spelling(data_type, BooleanType)
        return "BIT", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        """``VARCHAR(n)`` for both spellings.

        T-SQL writes neither ``CHARACTER VARYING`` nor ``CHARACTER``: the long
        forms are SQL's, not this backend's, so a portable spelling is
        normalised to the word the catalog reports.  An undeclared width is this
        dialect's **255** — which is a choice of this backend and *not* what T-SQL
        does, whose own default is 1; :meth:`type_parameter_defaults` writes that
        down with the measurement behind it.  The number is read from the same
        declaration rather than repeated here, because this fallback exists only
        for a type built without a dialect: a type bound to this one has already
        resolved to the declared 255 in its own ``length``, and the two answers
        must not be allowed to drift apart.

        A declared length is range-checked against the 8000-byte inline ceiling
        T-SQL documents; see :meth:`_check_length`, which also sets out why this
        backend checks the intersection of that page's two statements about the
        lower bound rather than picking one of them.
        """
        self._check_spelling(data_type, VarCharType)
        self._check_length("VARCHAR", data_type.length)
        length = data_type.length
        if length is None:
            length = self.type_parameter_defaults()["varchar"]["length"]
        return f"VARCHAR({length})", ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        """``CHAR(n)`` for both spellings, defaulting to ``CHAR(1)``.

        Fixed length: a shorter value is space-padded to ``n`` rather than
        stored as written, and the padding is why the concept is fixed-length
        rather than variable-length.  Declaring no length is ``CHAR(1)``, and here
        that is T-SQL's own default as well — measured, not assumed; see
        :meth:`type_parameter_defaults`.  As in
        :meth:`format_data_type_varchar` the fallback reads the one declaration,
        for a type built without a dialect.

        A declared length is range-checked exactly as :meth:`format_data_type_varchar`
        range-checks a ``VARCHAR`` one; see :meth:`_check_length`.
        """
        self._check_spelling(data_type, CharType)
        self._check_length("CHAR", data_type.length)
        length = data_type.length
        if length is None:
            length = self.type_parameter_defaults()["char"]["length"]
        return f"CHAR({length})", ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        """``NVARCHAR(MAX)`` for both spellings.

        Unbounded text is spelled ``NVARCHAR(MAX)`` on SQL Server, not ``TEXT``:
        ``TEXT`` is the deprecated non-Unicode type and cannot hold characters
        outside the database collation.  The dialect already stores ``json``,
        enums and byte strings here, and ``clob`` names the same unbounded
        concept, so it is accepted rather than refused.
        """
        self._check_spelling(data_type, TextType)
        return "NVARCHAR(MAX)", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        """``DATETIME2`` — T-SQL's own word for a datetime without an offset.

        The deprecated ``DATETIME`` and ``SMALLDATETIME`` are its ancestors, not
        its synonyms: they round seconds (or even minutes) differently, which is
        why they are separate parser branches rather than spellings of this
        concept.
        """
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server DATETIME2 fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"DATETIME2({data_type.precision})", ()
        return "DATETIME2", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server TIME fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"TIME({data_type.precision})", ()
        return "TIME", ()

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        """``DATETIME2`` — SQL Server renders this concept as its own datetime.

        Worth stating because it is the opposite of what the spelling suggests:
        T-SQL's ``TIMESTAMP`` is *not* a timestamp, it is the ``ROWVERSION``
        8-byte auto-incrementing counter, so a requested ``TIMESTAMP WITH TIME
        ZONE`` must not be confused with either of them.  The timezone-aware
        concept is :meth:`format_data_type_timestamptz`.
        """
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server DATETIME2 fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"DATETIME2({data_type.precision})", ()
        return "DATETIME2", ()

    def format_data_type_timestamptz(self, data_type: TimestampTzType) -> Tuple[str, tuple]:
        """``DATETIMEOFFSET`` — SQL Server's timezone-aware datetime.

        The concept is rendered, not substituted, because T-SQL really has the
        type: ``DATETIMEOFFSET`` keeps the local time *and* the offset, which is
        what distinguishes it from the ``DATETIME2`` above.  The one thing it
        does not keep is the zone *identifier* — there is no time-zone name in
        the type, so a column that needs one has to carry it separately.
        """
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server DATETIMEOFFSET fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"DATETIMEOFFSET({data_type.precision})", ()
        return "DATETIMEOFFSET", ()

    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        """``NVARCHAR(MAX)`` — SQL Server has no JSON *type*.

        JSON arrives in SQL Server 2016 as text in an ordinary column, and
        ``OPENJSON`` / ``JSON_VALUE`` / ``ISJSON`` are functions over that
        text, not a storage type.  So the concept is rendered as the text
        column that actually holds it, which is also why ``suggested_data_types``
        names this class for ``jsonb`` and ``array``.
        """
        return "NVARCHAR(MAX)", ()

    def format_data_type_xml(self, data_type: XmlType) -> Tuple[str, tuple]:
        """``XML`` — SQL Server has a native ``xml`` type.

        Unlike ``json``, this concept is not text here: the storage is a binary
        representation that supports ``.nodes()`` / ``.value()`` / ``.exist()``
        / ``.modify()``, so the XML concept is rendered rather than substituted
        with a string column.  An associated XML Schema Collection is a column
        attribute, so it does not appear here.
        """
        return "XML", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        """``VARBINARY(MAX)`` for both spellings.

        T-SQL's own name for the byte-string storage; ``BYTEA`` is PostgreSQL's
        and is accepted because it names the same concept, not because this
        backend writes it.  ``VARBINARY(MAX)`` is the 2 GB form — T-SQL's
        unbounded byte storage — and is what an unbounded blob is on this
        dialect.
        """
        self._check_spelling(data_type, BlobType)
        return "VARBINARY(MAX)", ()

    def format_data_type_custom(self, data_type: CustomType) -> Tuple[str, tuple]:
        return data_type.raw, ()

    # ------------------------------------------------------------------
    # supports_data_type_<name> — 1:1 with format_data_type_<name>
    # ------------------------------------------------------------------

    def supports_data_type_sqlserver_nvarchar(self) -> bool:
        return True

    def supports_data_type_sqlserver_nchar(self) -> bool:
        return True

    def supports_data_type_sqlserver_uniqueidentifier(self) -> bool:
        return True

    def supports_data_type_sqlserver_nvarchar_max(self) -> bool:
        return True

    def supports_data_type_sqlserver_varbinary(self) -> bool:
        return True

    def supports_data_type_sqlserver_varbinary_max(self) -> bool:
        return True

    def supports_data_type_sqlserver_xml(self) -> bool:
        return True

    def supports_data_type_sqlserver_tinyint(self) -> bool:
        return True

    def supports_data_type_sqlserver_bit(self) -> bool:
        return True

    def supports_data_type_sqlserver_image(self) -> bool:
        return True

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_tinyint(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_real(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return True

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    def supports_data_type_timestamptz(self) -> bool:
        """``DATETIMEOFFSET`` arrived with SQL Server 2008 (10.0).

        The concept is rendered rather than substituted, so this gate is the
        only thing standing between a 2005 dialect and a column the server will
        reject with 'DATETIMEOFFSET is not a recognized user-defined type'.  An
        unconditional ``True`` would send the DDL and let the server answer,
        which is the failure mode a capability question exists to prevent.
        """
        return self.version >= (10, 0, 0)

    def supports_data_type_json(self) -> bool:
        """Unconditional, because the storage this concept renders to has
        always existed.

        JSON itself arrived in SQL Server 2016, but a JSON *value* lives in an
        ordinary ``NVARCHAR(MAX)`` column, which is what
        :meth:`format_data_type_json` emits, and ``NVARCHAR(MAX)`` is a type
        from 2005.  Refusing the concept on a pre-2016 server would hide a key
        from ``supports_data_types()`` without changing what this dialect can
        actually write — the JSON *functions* are version-gated separately, in
        ``supports_json_function()``.
        """
        return True

    def supports_data_type_xml(self) -> bool:
        """SQL Server has had a native ``xml`` type since 2005 (9.0).

        Unconditional on the version rather than a gate, because the type is a
        core one for this engine — there is no fallback the type is being
        preferred over.
        """
        return True

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_custom(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # DDLTypeSupport — parsing
    # ------------------------------------------------------------------
    #
    # Canonicality (D8): one spelling in, its own concept class out, with the
    # spelling recorded on the instance.  Nothing here may yield a *different*
    # concept than the word it read — that is how ``char`` came to yield
    # ``VarCharType`` and ``date`` came to yield ``DateTimeType``.  A name this
    # dialect cannot map to a concept the framework models falls through to
    # ``CustomType``, which is honest ignorance rather than a wrong answer.

    _SQLSERVER_INTEGER_TYPES = re.compile(
        r"^(?:INT8|BIGINT|SMALLINT|INT2|TINYINT|INT1|INTEGER|INT)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_FLOAT_TYPES = re.compile(
        r"^(?:FLOAT|REAL|DOUBLE)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_DECIMAL_TYPES = re.compile(
        r"^(?:DECIMAL|NUMERIC|DEC|MONEY|SMALLMONEY)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_STRING_TYPES = re.compile(
        r"^(?:CHARACTER|NCHAR|VARCHAR|NVARCHAR|CHAR|CLOB|NTEXT|TEXT)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_DATE_TYPES = re.compile(
        r"^(?:DATETIMEOFFSET|DATETIME2|SMALLDATETIME|DATETIME|DATE)\b",
        re.IGNORECASE,
    )
    #: The plain calendar date, separated from the datetimes that share its
    #: letters.  ``startswith("DATE")`` cannot tell them apart — ``DATETIME``,
    #: ``DATETIME2`` and ``SMALLDATETIME`` all begin with ``DATE`` — so the
    #: check is anchored and word-bounded instead.
    _SQLSERVER_DATE_ONLY_TYPES = re.compile(
        r"^DATE\b",
        re.IGNORECASE,
    )
    _SQLSERVER_TIME_TYPES = re.compile(
        r"^(?:TIME)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_BIT_TYPES = re.compile(
        r"^(?:BIT|BOOL|BOOLEAN)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_BLOB_TYPES = re.compile(
        r"^(?:VARBINARY|IMAGE|BLOB|BYTEA)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_XML_TYPES = re.compile(
        r"^(?:XML)\b",
        re.IGNORECASE,
    )
    #: The declared argument list: ``(n)`` for a length or a precision,
    #: ``(p,s)`` for precision and scale.  Group 1 is always the first number,
    #: group 2 the scale when one was declared — which is why ``DECIMAL(10,2)``
    #: does not silently parse as ``DECIMAL``.
    _SQLSERVER_ARGUMENTS = re.compile(r"\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)")

    def parse_type(self, raw: str) -> DataType:
        from ..expression.types import (
            SQLServerBitType,
            SQLServerImageType,
            SQLServerNCharType,
            SQLServerNVarCharType,
            SQLServerTinyIntType,
            SQLServerUniqueIdentifierType,
            SQLServerVarBinaryMaxType,
            SQLServerVarBinaryType,
            SQLServerXmlType,
        )

        stripped = raw.strip()
        upper = stripped.upper()
        arguments = self._SQLSERVER_ARGUMENTS.search(stripped)
        length = int(arguments.group(1)) if arguments else None
        scale = int(arguments.group(2)) if arguments and arguments.group(2) else None

        # BIT — the boolean, not MySQL/PostgreSQL's bit string.  The spelling
        # recorded is the concept's own, so ``BOOLEAN`` and ``BOOL`` survive the
        # round trip; T-SQL's ``BIT`` belongs to ``SQLServerBitType``'s own
        # name, not to the concept's list.
        #
        # The lookup is on the whole stripped word and reads ``None`` for a
        # parenthesised form, which used to escape as a bare
        # ``KeyError: 'BIT(1)'``.  A width on ``bit`` is not a declaration
        # this server accepts: all three live instances (SQL Server 2019
        # 15.0.4465.1, 2022 16.0.4250.1, 2025 17.0.4035.5) refuse
        # ``CREATE TABLE t (b bit(1))`` with error 2716, "Cannot specify a
        # column width on data type bit."  So the parameter is answered with
        # the ``ValueError`` this module uses for a value the server itself
        # rejects (the same class as ``_check_length``), quoting the server's
        # answer rather than silently dropping the width.  It is deliberately
        # not ``InvalidTypeNameError``: ``bit(1)`` is a valid type *name*;
        # the server rejects its width.
        if self._SQLSERVER_BIT_TYPES.match(upper):
            spelling = {"BIT": "boolean", "BOOL": "bool",
                        "BOOLEAN": "boolean"}.get(upper)
            if spelling is None:
                raise ValueError(
                    f"{stripped!r} is not a declaration this server accepts: "
                    f"T-SQL's ``bit`` takes no width, and SQL Server refuses "
                    f"one with error 2716, 'Cannot specify a column width on "
                    f"data type bit.' (measured live on SQL Server 2019 "
                    f"(15.0.4465.1), 2022 (16.0.4250.1) and 2025 "
                    f"(17.0.4035.5)). Declare the bare word — ``bit``, or its "
                    f"accepted spellings ``bool`` and ``boolean`` — without "
                    f"parentheses."
                )
            return SQLServerBitType(dialect=self, spelling=spelling)

        # UNIQUEIDENTIFIER — the native GUID.
        if upper.startswith("UNIQUEIDENTIFIER"):
            return SQLServerUniqueIdentifierType(dialect=self)

        # XML — a binary XML representation, not a varchar (checked before the
        # string family because ``XML`` shares no prefix with any of it).
        if self._SQLSERVER_XML_TYPES.match(upper):
            return SQLServerXmlType(dialect=self)

        # Integer family: one class per width, and the spelling preserved.
        if self._SQLSERVER_INTEGER_TYPES.match(upper):
            if upper.startswith("INT8"):
                return BigIntType(dialect=self, spelling="int8")
            if upper.startswith("BIGINT"):
                return BigIntType(dialect=self, spelling="bigint")
            if upper.startswith("INT2"):
                return SmallIntType(dialect=self, spelling="int2")
            if upper.startswith("SMALLINT"):
                return SmallIntType(dialect=self, spelling="smallint")
            if upper.startswith("INT1"):
                return TinyIntType(dialect=self, spelling="int1")
            if upper.startswith("TINYINT"):
                return SQLServerTinyIntType(dialect=self)
            spelling = "integer" if upper.startswith("INTEGER") else "int"
            return IntegerType(dialect=self, spelling=spelling)

        # Float family.  ``DOUBLE`` / ``DOUBLE PRECISION`` is the concept SQL
        # names for 8-byte floating point, which T-SQL spells ``FLOAT(53)``.
        if self._SQLSERVER_FLOAT_TYPES.match(upper):
            if upper.startswith("DOUBLE"):
                spelling = "double precision" if "PRECISION" in upper else "double"
                return DoubleType(dialect=self, spelling=spelling)
            if upper.startswith("REAL"):
                return RealType(dialect=self)
            return FloatType(dialect=self, precision=length)

        # Decimal family.  ``MONEY`` / ``SMALLMONEY`` are deliberately *not*
        # spellings of this concept: they carry a fixed scale of 4 and a
        # currency-formatted result that the schema does not record.  Mapping
        # them to ``DecimalType`` loses that, and it stays because the framework
        # has no money concept this dialect could declare instead.
        if self._SQLSERVER_DECIMAL_TYPES.match(upper):
            if upper.startswith("MONEY") or upper.startswith("SMALLMONEY"):
                return DecimalType(dialect=self)
            if upper.startswith("NUMERIC"):
                spelling = "numeric"
            elif upper.startswith("DECIMAL"):
                spelling = "decimal"
            else:
                spelling = "dec"
            return DecimalType(dialect=self, precision=length, scale=scale,
                               spelling=spelling)

        # String family.  Fixed length and variable length are different
        # concepts, so ``CHAR`` never yields a VarCharType and ``VARCHAR`` never
        # yields a CharType.
        #
        # A word that carries no ``n`` is completed from
        # ``type_parameter_defaults()`` rather than from a literal here, so the
        # parser and the formatter cannot disagree about what an unsized
        # declaration means on this server.  ``CHARACTER VARYING`` and
        # ``CHARACTER`` need no such completion: their concepts are the ones that
        # already resolve to a width from the dialect they are constructed with,
        # so the bare word arrives as a bound type whose width is the declared
        # one.
        if self._SQLSERVER_STRING_TYPES.match(upper):
            # ``(MAX)`` lifts the length cap rather than setting one, in either
            # character set, so it is unbounded text and not a 255-char column.
            unbounded = arguments is None and "MAX" in upper
            if upper.startswith("NCHAR"):
                return SQLServerNCharType(
                    dialect=self,
                    length=length or self.type_parameter_defaults()["sqlserver_nchar"]["length"])
            if upper.startswith("NVARCHAR"):
                if unbounded:
                    return TextType(dialect=self)
                return SQLServerNVarCharType(
                    dialect=self,
                    length=length or self.type_parameter_defaults()["sqlserver_nvarchar"]["length"])
            if upper.startswith("VARCHAR"):
                if unbounded:
                    return TextType(dialect=self)
                return VarCharType(
                    dialect=self,
                    length=length or self.type_parameter_defaults()["varchar"]["length"])
            if upper.startswith("CHARACTER VARYING"):
                return VarCharType(dialect=self, length=length,
                                   spelling="character varying")
            if upper.startswith("CHARACTER"):
                return CharType(dialect=self, length=length, spelling="character")
            if upper.startswith("CHAR"):
                return CharType(dialect=self, length=length)
            # ``CLOB`` / ``TEXT`` / ``NTEXT`` are all unbounded text: the first
            # is the portable spelling, the other two the deprecated T-SQL
            # ones, and all three render ``NVARCHAR(MAX)``.
            spelling = "clob" if upper.startswith("CLOB") else "text"
            return TextType(dialect=self, spelling=spelling)

        # Date/time family.  ``DATE`` is its own concept — a calendar date with
        # no time of day — and T-SQL ``TIMESTAMP`` is ``ROWVERSION``, an
        # 8-byte auto-incrementing counter that is *not* a timestamp; with no
        # rowversion concept to declare, that name falls through to
        # ``CustomType`` rather than being filed under datetime.
        if self._SQLSERVER_DATE_TYPES.match(upper):
            if upper.startswith("DATETIMEOFFSET"):
                return TimestampTzType(dialect=self, precision=length)
            if self._SQLSERVER_DATE_ONLY_TYPES.match(upper):
                return DateType(dialect=self)
            return DateTimeType(dialect=self, precision=length)

        if self._SQLSERVER_TIME_TYPES.match(upper):
            return TimeType(dialect=self, precision=length)

        # Byte-string family.  ``VARBINARY(MAX)`` is the unbounded declaration
        # and not a 255-byte one, so it gets its own class.
        if self._SQLSERVER_BLOB_TYPES.match(upper):
            if upper.startswith("VARBINARY"):
                if arguments is None and "MAX" in upper:
                    return SQLServerVarBinaryMaxType(dialect=self)
                return SQLServerVarBinaryType(dialect=self, length=length)
            if upper.startswith("IMAGE"):
                return SQLServerImageType(dialect=self)
            spelling = "bytea" if upper.startswith("BYTEA") else "blob"
            return BlobType(dialect=self, spelling=spelling)

        return CustomType(dialect=self, raw=stripped)
