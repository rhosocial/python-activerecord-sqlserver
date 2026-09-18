from dataclasses import dataclass
from typing import Optional

from rhosocial.activerecord.backend.options import ExecutionOptions


@dataclass
class SQLServerExecutionOptions(ExecutionOptions):
    noscan: Optional[bool] = None
