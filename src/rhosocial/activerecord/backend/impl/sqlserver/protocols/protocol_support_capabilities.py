# sqlserver/protocols/protocol_support_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class SQLServerProtocolSupportSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_tablesample_clause(self, sample: int, percentage: bool=False, repeatable: Optional[int]=None) -> str:
        ...  # pragma: no cover
    def format_select_head(self, expr: Any) -> str:
        ...  # pragma: no cover
    def supports_json_function(self, function_name: str) -> bool:
        ...  # pragma: no cover
    def format_json_extract(self, json_doc: str, path: str, paths: Optional[List[str]]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_unquote(self, json_val: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_object(self, key_value_pairs: List[Tuple[str, Any]]) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_array(self, values: List[Any]) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_contains(self, target: str, candidate: str, path: Optional[str]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_set(self, json_doc: str, path: str, value: Any, path_value_pairs: Optional[List[Tuple[str, Any]]]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_remove(self, json_doc: str, path: str, paths: Optional[List[str]]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_type(self, json_val: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_valid(self, json_val: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_json_search(self, json_doc: str, search_str: str, path: Optional[str]=None, all_: bool=False) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def supports_set_type(self) -> bool:
        ...  # pragma: no cover
    def format_set_literal(self, values: List[str], column_values: Optional[List[str]]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_find_in_set(self, value: str, set_column: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_set_contains(self, column: str, values: List[str]) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def supports_spatial_type(self, type_name: str) -> bool:
        ...  # pragma: no cover
    def supports_spatial_index(self) -> bool:
        ...  # pragma: no cover
    def supports_geojson(self) -> bool:
        ...  # pragma: no cover
    def format_spatial_literal(self, wkt: str, srid: Optional[int]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_geom_from_text(self, wkt: str, srid: Optional[int]=None) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_as_text(self, geom: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_as_geojson(self, geom: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_distance(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_within(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_contains(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_distance_sphere(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_st_intersects(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_create_spatial_index(self, index: str, table: str, column: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
