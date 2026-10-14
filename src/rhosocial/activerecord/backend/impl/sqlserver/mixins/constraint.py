# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/constraint.py
"""SQL Server constraint capability declarations.

Every value in this module is grounded in a live measurement against the
instance ``tests/config/sqlserver_scenarios.yaml`` names ``sqlserver_2019``:

* **SQL Server 2019 (RTM-CU32-GDR), 15.0.4465.1, Developer Edition**,
  reached at ``127.0.0.1:11433`` with pyodbc 5.3.0 + ``ODBC Driver 17 for
  SQL Server``.

Message numbers and wordings below are the server's own, as returned in the
driver's error payload. Nothing here is transcribed from documentation; the
two places where a *documentation* claim is carried rather than a measurement
(``DROP CONSTRAINT IF EXISTS`` and ``DROP COLUMN IF EXISTS`` being available
"since 2016") say so where they are stated, in
``alter_table_modifier.py``.

The load-bearing shape of T-SQL, stated once here so the individual docstrings
can stay short: **SQL Server has no SQL-standard constraint clauses at all.**
``ENFORCED`` / ``NOT ENFORCED``, ``DEFERRABLE`` / ``INITIALLY``,
``NOT VALID``, ``VALIDATE CONSTRAINT`` and ``ENABLE`` / ``DISABLE CONSTRAINT``
are all syntax errors (Msg 102 or 156) -- not accepted-and-ignored.  What T-SQL
offers instead is a *state* vocabulary, and it is not interchangeable with
the clause vocabulary the core protocol is named after:

* ``ALTER TABLE ... WITH NOCHECK ADD CONSTRAINT ...`` -- accepted, leaves the
  new constraint not trusted (``is_not_trusted = 1``).
* ``ALTER TABLE ... NOCHECK CONSTRAINT name`` -- accepted, sets
  ``is_not_trusted = 1`` **and** ``is_disabled = 1``.  Works on both CHECK
  and FOREIGN KEY constraints.
* ``ALTER TABLE ... CHECK CONSTRAINT name`` and
  ``WITH CHECK CHECK CONSTRAINT name`` -- accepted, re-validates existing rows
  and clears ``is_not_trusted`` / ``is_disabled``.
* ``NOT FOR REPLICATION`` -- accepted at ADD CONSTRAINT time on both a foreign
  key and a CHECK, and it sets ``is_not_for_replication = 1`` **with**
  ``is_not_trusted = 1``.  On CHECK the spelling precedes the parenthesised
  condition: ``CHECK NOT FOR REPLICATION (c > 0)``.

Naming note: the switches for the state vocabulary
(``supports_enable_disable_constraint``, ``supports_rename_constraint``) use
the names from ``.claude/plan/2026-10-11/sqlserver-constraint-coverage.md``.
The core ``AlterTableConstraintSupport`` protocol they belong to has not
landed yet, so **core may still rename them**; the measured value is what
matters and is asserted in the tests either way.

Where the standard clause *is* answered by a probe and the *kind* is not
(``supports_constraint_enforced``, ``supports_deferrable_constraint``,
``supports_alter_constraint_enforced``, ``supports_constraint_novalidate``,
``supports_validate_constraint``), the answer is ``False`` for every kind, so
there is nothing left to narrow and this package declares **no** ``_require_*``
helper.  A narrowing helper earns its place when the probe answers True and
the *kind* is what turns it away -- SQL Server's one real narrowing is the
column-level ``REFERENCES`` clause, and it is a formatter override
(:meth:`SQLServerConstraintMixin.format_column_fk_constraint`) because the
probe it has to disagree with is the table-level one.

The trait refusals live at the two public seams, both of which are named
rather than private: :meth:`SQLServerConstraintMixin.format_column_constraint`
for the column level, and ``SQLServerDialect.format_table_constraint`` (which
also owns the memory-optimized ``NONCLUSTERED`` spellings, so it cannot move
into this mixin) for the table level.  Both go through
:meth:`SQLServerConstraintMixin._refuse_constraint_traits` so the two levels
cannot drift apart.
"""

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        ColumnConstraint,
        ColumnForeignKeyConstraint,
    )


class SQLServerConstraintMixin:
    """SQL Server constraint capability declarations."""

    def supports_constraint_enforced(self) -> bool:
        """False: T-SQL has no ``ENFORCED`` / ``NOT ENFORCED`` clause.

        Measured on 2019 (15.0.4465.1), against a CHECK constraint::

            ALTER TABLE dbo.probe_t ADD CONSTRAINT ck10 CHECK (c > 0) NOT ENFORCED
            -> Incorrect syntax near the keyword 'NOT'. (156)
            ALTER TABLE dbo.probe_t ADD CONSTRAINT ck11 CHECK (c > 0) ENFORCED
            -> Incorrect syntax near 'ENFORCED'. (102)

        Enforcement control is a *state* on the constraint in T-SQL
        (``sys.check_constraints.is_not_trusted`` / ``is_disabled``), not a
        clause inside it; see the module docstring.  An explicitly requested
        spelling is refused by name at the two public seams
        (:meth:`SQLServerConstraintMixin.format_column_constraint` and
        ``SQLServerDialect.format_table_constraint``) rather than silently
        dropped.
        """
        return False

    def supports_fk_match(self) -> bool:
        """False: T-SQL has no ``MATCH {SIMPLE|PARTIAL|FULL}`` clause.

        Measured on 2019 (15.0.4465.1)::

            ALTER TABLE dbo.probe_t ADD CONSTRAINT fk5 FOREIGN KEY (id)
                REFERENCES dbo.probe_r (id) MATCH FULL
            -> Incorrect syntax near 'MATCH'. (102)

        Unlike MySQL 8 (which parses ``MATCH FULL`` and then silently drops
        it), SQL Server rejects it at the parser, so a renderer that emitted
        it would fail loudly rather than mislead.
        """
        return False

    def supports_deferrable_constraint(self) -> bool:
        """False: T-SQL has neither ``DEFERRABLE`` nor ``INITIALLY``.

        Measured on 2019 (15.0.4465.1), against a CHECK constraint::

            ALTER TABLE dbo.probe_t ADD CONSTRAINT ck9  CHECK (c > 0) DEFERRABLE
            -> Incorrect syntax near 'DEFERRABLE'. (102)
            ALTER TABLE dbo.probe_t ADD CONSTRAINT ck12 CHECK (c > 0) NOT DEFERRABLE
            -> Incorrect syntax near the keyword 'NOT'. (156)

        Constraint checking is always immediate.  ``NOCHECK CONSTRAINT``
        *disables* a constraint until it is re-checked -- it does not defer
        evaluation to end of transaction, so it is not a fallback for
        ``DEFERRABLE``.
        """
        return False

    def supports_add_constraint(self) -> bool:
        """True: ``ALTER TABLE ... ADD CONSTRAINT`` covers all four constraint kinds.

        Measured on 2019 (15.0.4465.1), all four accepted at ADD CONSTRAINT
        time::

            ALTER TABLE dbo.probe_t ADD CONSTRAINT ck1 CHECK NOT FOR REPLICATION (c > 0)
            ALTER TABLE dbo.probe_t ADD CONSTRAINT pk1 PRIMARY KEY (id ASC, s DESC)
            ALTER TABLE dbo.probe_t ADD CONSTRAINT uq1 UNIQUE (id ASC, s DESC)
            ALTER TABLE dbo.probe_t ADD CONSTRAINT fk1 FOREIGN KEY (id)
                REFERENCES dbo.probe_r (id) NOT FOR REPLICATION

        Two facts come with it: a table may hold **only one** primary key
        (a second ``ADD CONSTRAINT ... PRIMARY KEY`` is
        ``Table 'probe_t' already has a primary key defined on it. (1779)``
        plus ``Could not create constraint or index. (1750)``), and the
        ``ASC`` / ``DESC`` direction on a table-level PRIMARY KEY / UNIQUE is
        not ignored -- ``sys.index_columns.is_descending_key`` reads ``True``
        for the ``DESC`` column.

        Core already defaults this to ``True``; the declaration pins it to the
        measurement.
        """
        return True

    def supports_drop_constraint(self) -> bool:
        """True: ``ALTER TABLE ... DROP CONSTRAINT name`` is accepted.

        Measured on 2019 (15.0.4465.1)::

            ALTER TABLE dbo.probe_t DROP CONSTRAINT ck2    -- accepted
            ALTER TABLE dbo.probe_t DROP CONSTRAINT nope
            -> 'nope' is not a constraint. (3728)
            -> Could not drop constraint. See previous errors. (3727)

        So a missing constraint is an **error**, not a silent no-op: the
        idempotent path is ``DROP CONSTRAINT IF EXISTS``, declared separately
        by ``SQLServerAlterColumnModifierMixin``.
        """
        return True

    def supports_alter_constraint_enforced(self) -> bool:
        """False: ``ALTER TABLE ... ALTER CONSTRAINT`` is not T-SQL at all.

        Measured on 2019 (15.0.4465.1)::

            ALTER TABLE dbo.probe_t ALTER CONSTRAINT fk4 ENFORCED
            -> Incorrect syntax near the keyword 'CONSTRAINT'. (156)

        There is no ALTER-side counterpart to the ADD-side state vocabulary
        either; ``NOCHECK CONSTRAINT`` / ``CHECK CONSTRAINT`` change state,
        they do not re-declare the constraint.  Core defaults this to
        ``False`` as well; the declaration records the measurement.

        The signature is ``(self)``.  A probe answers one question -- "is this
        capability family present on this server" -- and the kind is not part
        of that question, so the parameter this switch used to take had no
        answer to give that the parameter-less form did not already give.
        """
        return False

    def supports_validate_constraint(self) -> bool:
        """False: T-SQL has no ``VALIDATE CONSTRAINT`` clause.

        Measured on 2019 (15.0.4465.1)::

            ALTER TABLE dbo.probe_t VALIDATE CONSTRAINT fk4
            -> Incorrect syntax near 'VALIDATE'. (102)

        The measured equivalent of "validate now" is
        ``ALTER TABLE ... CHECK CONSTRAINT name`` or
        ``WITH CHECK CHECK CONSTRAINT name``, both accepted, both clearing
        ``is_not_trusted``.
        """
        return False

    def supports_constraint_novalidate(self) -> bool:
        """False: T-SQL has no ``NOT VALID`` clause.

        Measured on 2019 (15.0.4465.1)::

            ALTER TABLE dbo.probe_t ADD CONSTRAINT ck8 CHECK (c > 0) NOT VALID
            -> Incorrect syntax near the keyword 'NOT'. (156)

        A not-yet-validated constraint is expressed the other way round:
        ``ALTER TABLE ... WITH NOCHECK ADD CONSTRAINT ...`` is accepted and
        leaves ``sys.check_constraints.is_not_trusted = 1``.  That is the
        closest T-SQL analogue to ``NOT VALID`` -- an ADD-time spelling, not a
        clause trailing the constraint.
        """
        return False

    def supports_enable_disable_constraint(self) -> bool:
        """False: ``ENABLE CONSTRAINT`` / ``DISABLE CONSTRAINT`` are not T-SQL keywords.

        Measured on 2019 (15.0.4465.1), against a live CHECK constraint::

            ALTER TABLE dbo.probe_t ENABLE  CONSTRAINT ck2
            -> Incorrect syntax near the keyword 'CONSTRAINT'. (156)
            ALTER TABLE dbo.probe_t DISABLE CONSTRAINT ck2
            -> Incorrect syntax near the keyword 'CONSTRAINT'. (156)

        Of the ten backends only Oracle spells ``ENABLE`` / ``DISABLE
        CONSTRAINT``; SQL Server's state-changing pair is
        ``NOCHECK CONSTRAINT name`` (disable) and
        ``CHECK CONSTRAINT name`` (re-enable), which also **re-validate**
        rather than merely flipping a flag.  PostgreSQL's ``ENABLE TRIGGER``
        and other near-relative spellings do not make this one exist.

        Name note: this is the ``AlterTableConstraintSupport`` switch named in
        the constraint-coverage plan; the core protocol has not landed it yet,
        so core may still rename this.
        """
        return False

    def supports_rename_constraint(self) -> bool:
        """False: no ``RENAME CONSTRAINT ... TO ...`` clause, and ``sp_rename`` is narrower than it looks.

        Measured on 2019 (15.0.4465.1).  The three-argument ``sp_rename``
        form fails for every constraint kind, with or without a schema
        qualifier::

            EXEC sp_rename 'dbo.probe_key.pk_new', 'pk_newer', 'OBJECT'
            -> Either the parameter @objname is ambiguous or the claimed
               @objtype (OBJECT) is wrong. (15248)

        The **two-argument** form (no ``@objtype``) is the one that works,
        and it is counter-intuitive in two ways: passing ``@objtype`` is what
        breaks it, and it only reaches **PRIMARY KEY and UNIQUE** constraints::

            EXEC sp_rename 'dbo.probe_key.pk_old', 'pk_new'   -- accepted,
                                                               -- renamed in sys.key_constraints
            EXEC sp_rename 'dbo.probe_key.uq_old', 'uq_new'   -- accepted
            EXEC sp_rename 'dbo.probe_ck.ck_old', 'ck_new'    -- CHECK
            -> No item by the name of 'dbo.probe_ck.ck_old' could be found in
               the current database 'master', given that @itemtype was input
               as '(null)'. (15225)
            EXEC sp_rename 'dbo.probe_key.fk_old', 'fk_new'   -- FOREIGN KEY
            -> No item by the name of 'dbo.probe_key.fk_old' could be found ... (15225)

        ``@objtype = 'CONSTRAINT'`` is not even a recognised value
        (``Explicit @objtype 'CONSTRAINT' is unrecognized. (15249)``).

        So: no ALTER-level rename (hence ``False``), and the escape hatch is a
        stored procedure, two-argument form, primary-key/unique only -- a
        rename that has to be re-implemented per constraint kind is not a
        dialect capability this switch can promise generically.
        """
        return False

    # ------------------------------------------------------------------
    # Narrowing seams
    # ------------------------------------------------------------------

    def format_column_constraint(
        self,
        constraint: "ColumnConstraint",
    ) -> Tuple[str, tuple]:
        """Refuse the SQL-standard traits on a column constraint, by name.

        The public seam, not ``_format_constraint_enforcement``: that private
        hook is shared with the table-level trait renderer, so an override
        there would have to tell the two families apart by hand.  Overriding
        the column seam makes the family the override's own business.

        Every trait asked for here is refused before delegation, with the
        spelling the caller asked for quoted in the message, so the
        ``DEFERRABLE`` / ``NOT DEFERRABLE`` and ``ENFORCED`` / ``NOT ENFORCED``
        pairs stay distinguishable (see ``test_clause_pair_guard_sqlserver``).
        The refusal is the measured one -- Msg 102 / 156 for all four
        spellings on 2019.

        The branch, not a tag, says which kind this is; the ``CONSTRAINT
        <name>`` prefix and the branch body are core's to render.
        """
        self._refuse_constraint_traits(
            constraint,
            deferrable=constraint.deferrable,
            not_deferrable=constraint.not_deferrable,
            initially_deferred=constraint.initially_deferred,
            initially_immediate=constraint.initially_immediate,
            enforced=constraint.enforced,
            not_enforced=constraint.not_enforced,
        )
        return super().format_column_constraint(constraint)

    def format_column_fk_constraint(
        self,
        constraint: "ColumnForeignKeyConstraint",
    ) -> Tuple[str, tuple]:
        """Refuse the column-level ``REFERENCES`` clause.

        **The known coupling this has to work around.** Core's
        ``format_column_fk_constraint`` gates the column-level grammar on
        ``supports_foreign_key_constraint()``, which is the *table-level*
        probe -- and SQL Server needs that probe to be ``True``:
        ``ALTER TABLE ... ADD CONSTRAINT fk1 FOREIGN KEY (id) REFERENCES
        dbo.probe_r (id)`` is accepted on 2019 (see
        :meth:`supports_add_constraint`).  So the probe cannot be flipped to
        turn the column level off, and the two levels have no separate probes
        yet.  Until they do, this override is where the column-level refusal
        lives: it is the public formatter for the column ``REFERENCES``
        branch, so narrowing here needs no private hook and no new probe.

        A column-level reference is written as ``col INT REFERENCES t (c)``,
        and T-SQL's column grammar has no ``REFERENCES`` production: a table
        constraint is the only spelling, which is what
        :meth:`format_table_foreign_key_constraint` renders.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        raise UnsupportedFeatureError(
            self.name,
            "REFERENCES column constraint",
            f"{self.name} does not support a column-level REFERENCES "
            f"constraint; declare the FOREIGN KEY as a table constraint.",
        )

    def _refuse_constraint_traits(
        self,
        constraint,
        *,
        deferrable: bool,
        not_deferrable: bool,
        initially_deferred: bool,
        initially_immediate: bool,
        enforced: bool,
        not_enforced: bool,
    ) -> None:
        """Raise on any SQL-standard constraint trait SQL Server cannot spell.

        One place for the four refusals so the column seam and the table seam
        cannot drift apart: the message quotes the *requested* spelling, so
        ``DEFERRABLE`` and ``NOT DEFERRABLE`` (and ``ENFORCED`` /
        ``NOT ENFORCED``) are distinguishable in the error.

        Measured on SQL Server 2019 (15.0.4465.1): every one of the four
        spellings is a parser error (Msg 102 or 156), not an
        accepted-and-ignored clause.  So this is a refusal, not a narrowing:
        there is no kind for which T-SQL accepts the trait.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        for wants, spelling in (
            (enforced or not_enforced, "ENFORCED" if enforced else "NOT ENFORCED"),
            (deferrable or not_deferrable, "DEFERRABLE" if deferrable else "NOT DEFERRABLE"),
            (
                initially_deferred or initially_immediate,
                "INITIALLY DEFERRED" if initially_deferred else "INITIALLY IMMEDIATE",
            ),
        ):
            if not wants:
                continue
            raise UnsupportedFeatureError(
                self.name,
                f"constraint {spelling}",
                f"{self.name} does not support the {spelling} constraint.",
            )
