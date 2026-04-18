# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/introspector.py
"""SQL Server schema introspector implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SQLServerColumnInfo:
    """Column metadata."""
    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    is_identity: bool = False
    is_computed: bool = False
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    collation: Optional[str] = None


@dataclass
class SQLServerIndexInfo:
    """Index metadata."""
    name: str
    table_name: str
    is_unique: bool
    is_primary_key: bool
    is_clustered: bool
    columns: List[str]
    is_disabled: bool = False


@dataclass
class SQLServerForeignKeyInfo:
    """Foreign key metadata."""
    name: str
    table_name: str
    columns: List[str]
    referenced_table: str
    referenced_columns: List[str]
    on_delete: str
    on_update: str


class SyncSQLServerIntrospector:
    """Synchronous SQL Server introspector.
    
    Provides methods for querying SQL Server system catalogs
    to retrieve schema metadata.
    """
    
    def __init__(self, backend, executor):
        self._backend = backend
        self._executor = executor
    
    def get_tables(self, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get all tables in schema.
        
        Args:
            schema: Schema name (default: dbo)
        
        Returns:
            List of table information dictionaries
        """
        sql = """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = ?
            ORDER BY TABLE_NAME
        """
        return self._executor.execute(sql, (schema,))
    
    def get_columns(self, table: str, schema: str = "dbo") -> List[SQLServerColumnInfo]:
        """Get columns for a table.
        
        Args:
            table: Table name
            schema: Schema name (default: dbo)
        
        Returns:
            List of SQLServerColumnInfo objects
        """
        sql = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME), COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY,
                COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME), COLUMN_NAME, 'IsComputed') AS IS_COMPUTED,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                COLLATION_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """
        rows = self._executor.execute(sql, (schema, table))
        return [SQLServerColumnInfo(
            name=row.get('COLUMN_NAME', ''),
            data_type=row.get('DATA_TYPE', ''),
            is_nullable=row.get('IS_NULLABLE', 'YES') == 'YES',
            default_value=row.get('COLUMN_DEFAULT'),
            is_identity=bool(row.get('IS_IDENTITY', 0)),
            is_computed=bool(row.get('IS_COMPUTED', 0)),
            max_length=row.get('CHARACTER_MAXIMUM_LENGTH'),
            precision=row.get('NUMERIC_PRECISION'),
            scale=row.get('NUMERIC_SCALE'),
            collation=row.get('COLLATION_NAME')
        ) for row in rows]
    
    def get_indexes(self, table: str, schema: str = "dbo") -> List[SQLServerIndexInfo]:
        """Get indexes for a table.
        
        Args:
            table: Table name
            schema: Schema name (default: dbo)
        
        Returns:
            List of SQLServerIndexInfo objects
        """
        sql = """
            SELECT 
                i.name AS index_name,
                i.is_unique,
                i.is_primary_key,
                i.type_desc AS index_type,
                i.is_disabled,
                STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
            FROM sys.indexes i
            INNER JOIN sys.tables t ON i.object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE s.name = ? AND t.name = ?
            GROUP BY i.name, i.is_unique, i.is_primary_key, i.type_desc, i.is_disabled
            ORDER BY i.name
        """
        rows = self._executor.execute(sql, (schema, table))
        return [SQLServerIndexInfo(
            name=row.get('index_name', ''),
            table_name=table,
            is_unique=bool(row.get('is_unique', 0)),
            is_primary_key=bool(row.get('is_primary_key', 0)),
            is_clustered=row.get('index_type', '') == 'CLUSTERED',
            columns=row.get('columns', '').split(',') if row.get('columns') else [],
            is_disabled=bool(row.get('is_disabled', 0))
        ) for row in rows]
    
    def get_foreign_keys(self, table: str, schema: str = "dbo") -> List[SQLServerForeignKeyInfo]:
        """Get foreign keys for a table.
        
        Args:
            table: Table name
            schema: Schema name (default: dbo)
        
        Returns:
            List of SQLServerForeignKeyInfo objects
        """
        sql = """
            SELECT 
                fk.name AS fk_name,
                OBJECT_NAME(fk.parent_object_id) AS table_name,
                STRING_AGG(COL_NAME(fc.parent_object_id, fc.parent_column_id), ',') AS columns,
                OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
                STRING_AGG(COL_NAME(fc.referenced_object_id, fc.referenced_column_id), ',') AS referenced_columns,
                fk.delete_referential_action_desc AS on_delete,
                fk.update_referential_action_desc AS on_update
            FROM sys.foreign_keys fk
            INNER JOIN sys.foreign_key_columns fc ON fk.object_id = fc.constraint_object_id
            INNER JOIN sys.tables t ON fk.parent_object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            GROUP BY fk.name, fk.parent_object_id, fk.referenced_object_id, 
                     fk.delete_referential_action_desc, fk.update_referential_action_desc
        """
        rows = self._executor.execute(sql, (schema, table))
        return [SQLServerForeignKeyInfo(
            name=row.get('fk_name', ''),
            table_name=row.get('table_name', ''),
            columns=row.get('columns', '').split(',') if row.get('columns') else [],
            referenced_table=row.get('referenced_table', ''),
            referenced_columns=row.get('referenced_columns', '').split(',') if row.get('referenced_columns') else [],
            on_delete=row.get('on_delete', 'NO_ACTION'),
            on_update=row.get('on_update', 'NO_ACTION')
        ) for row in rows]
    
    def get_constraints(self, table: str, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get constraints for a table.
        
        Args:
            table: Table name
            schema: Schema name (default: dbo)
        
        Returns:
            List of constraint information dictionaries
        """
        sql = """
            SELECT 
                tc.CONSTRAINT_NAME,
                tc.CONSTRAINT_TYPE,
                tc.IS_DEFERRABLE,
                tc.INITIALLY_DEFERRED
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            WHERE tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
            ORDER BY tc.CONSTRAINT_NAME
        """
        return self._executor.execute(sql, (schema, table))
    
    def get_views(self, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get views in schema.
        
        Args:
            schema: Schema name (default: dbo)
        
        Returns:
            List of view information dictionaries
        """
        sql = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = ?
            ORDER BY TABLE_NAME
        """
        return self._executor.execute(sql, (schema,))
    
    def get_sequences(self, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get sequences (SQL Server 2012+).
        
        Args:
            schema: Schema name (default: dbo)
        
        Returns:
            List of sequence information dictionaries
        """
        sql = """
            SELECT 
                name,
                schema_id,
                start_value,
                increment,
                minimum_value,
                maximum_value,
                is_cycling,
                current_value
            FROM sys.sequences
            WHERE schema_id = SCHEMA_ID(?)
        """
        return self._executor.execute(sql, (schema,))
    
    def get_procedures(self, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get stored procedures in schema.
        
        Args:
            schema: Schema name (default: dbo)
        
        Returns:
            List of procedure information dictionaries
        """
        sql = """
            SELECT ROUTINE_NAME
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_SCHEMA = ? AND ROUTINE_TYPE = 'PROCEDURE'
            ORDER BY ROUTINE_NAME
        """
        return self._executor.execute(sql, (schema,))
    
    def get_functions(self, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get user-defined functions in schema.
        
        Args:
            schema: Schema name (default: dbo)
        
        Returns:
            List of function information dictionaries
        """
        sql = """
            SELECT ROUTINE_NAME, ROUTINE_TYPE
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_SCHEMA = ? AND ROUTINE_TYPE = 'FUNCTION'
            ORDER BY ROUTINE_NAME
        """
        return self._executor.execute(sql, (schema,))
    
    def get_triggers(self, table: str, schema: str = "dbo") -> List[Dict[str, Any]]:
        """Get triggers for a table.
        
        Args:
            table: Table name
            schema: Schema name (default: dbo)
        
        Returns:
            List of trigger information dictionaries
        """
        sql = """
            SELECT 
                tr.name AS trigger_name,
                tr.is_disabled,
                tr.is_instead_of_trigger,
                OBJECT_NAME(tr.parent_id) AS table_name
            FROM sys.triggers tr
            INNER JOIN sys.tables t ON tr.parent_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            ORDER BY tr.name
        """
        return self._executor.execute(sql, (schema, table))
    
    def get_table_size(self, table: str, schema: str = "dbo") -> Dict[str, int]:
        """Get table size information.
        
        Args:
            table: Table name
            schema: Schema name (default: dbo)
        
        Returns:
            Dict with size information (reserved_bytes, used_bytes, row_count)
        """
        sql = """
            SELECT 
                SUM(reserved_page_count) * 8 * 1024 AS reserved_bytes,
                SUM(used_page_count) * 8 * 1024 AS used_bytes,
                SUM(row_count) AS row_count
            FROM sys.dm_db_partition_stats ps
            INNER JOIN sys.tables t ON ps.object_id = t.object_id
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
        """
        result = self._executor.execute(sql, (schema, table))
        return result[0] if result else {"reserved_bytes": 0, "used_bytes": 0, "row_count": 0}
