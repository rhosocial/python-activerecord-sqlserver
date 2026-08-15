# src/rhosocial/activerecord/backend/impl/sqlserver/explain/types.py
"""SQL Server EXPLAIN result type definitions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SQLServerExplainRow:
    """Row from STATISTICS PROFILE output.
    
    SQL Server provides execution plan information via STATISTICS PROFILE
    which returns detailed information about each operation.
    """
    
    execute_count: int = 0
    rows: int = 0
    stmt_text: str = ""
    estimate_rows: float = 0.0
    estimate_io: float = 0.0
    estimate_cpu: float = 0.0
    total_subtree_cost: float = 0.0
    avg_row_size: int = 0
    warnings: Optional[str] = None
    
    def __post_init__(self):
        pass


@dataclass
class SQLServerEstimateRow:
    """Row from SET SHOWPLAN_XML or estimated execution plan.
    
    Contains estimated execution statistics from the optimizer.
    """
    
    estimate_executions: Optional[float] = None
    estimate_rows: Optional[float] = None
    estimate_io_cost: Optional[float] = None
    estimate_cpu_cost: Optional[float] = None
    total_subtree_cost: Optional[float] = None
    logical_operation: Optional[str] = None
    physical_operation: Optional[str] = None
    avg_row_size: Optional[int] = None


@dataclass
class SQLServerExplainResult:
    """Result of EXPLAIN query.
    
    SQL Server provides execution plans in multiple formats:
    - Estimated plan: SET SHOWPLAN_XML ON
    - Actual plan: SET STATISTICS PROFILE ON
    - XML format: sys.dm_exec_query_plan
    
    Attributes:
        raw_rows: Raw result rows from the EXPLAIN query
        sql: Original SQL query
        duration: Query duration in seconds
        rows: Parsed explain rows
        xml_plan: XML execution plan (if available)
        estimated_cost: Total estimated cost
        missing_indexes: Suggested indexes for optimization
    """
    
    raw_rows: List[Dict[str, Any]]
    sql: str
    duration: float
    rows: List[SQLServerExplainRow] = field(default_factory=list)
    xml_plan: Optional[str] = None
    estimated_cost: Optional[float] = None
    missing_indexes: Optional[List[Dict[str, Any]]] = None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution plan.
        
        Returns:
            Dict containing key metrics from the execution plan
        """
        total_cost = sum(r.total_subtree_cost for r in self.rows if r.total_subtree_cost)
        total_rows = sum(r.rows for r in self.rows if r.rows)
        
        return {
            "total_cost": total_cost,
            "total_rows": total_rows,
            "row_count": len(self.rows),
            "has_warnings": any(r.warnings for r in self.rows if r.warnings),
            "duration": self.duration,
        }
    
    def get_operations(self) -> List[str]:
        """Get list of operations in the execution plan.
        
        Returns:
            List of operation names (from stmt_text)
        """
        operations = []
        seen = set()
        
        for row in self.rows:
            op = row.stmt_text.strip() if row.stmt_text else ""
            if op and op not in seen:
                operations.append(op)
                seen.add(op)
        
        return operations
    
    def get_warnings(self) -> List[str]:
        """Get list of warnings from the execution plan.
        
        Returns:
            List of warning messages
        """
        warnings = []
        for row in self.rows:
            if row.warnings:
                warnings.append(row.warnings)
        return warnings
