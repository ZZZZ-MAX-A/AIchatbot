from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    INTERNAL = "internal"
    READ_LOCAL = "read_local"
    READ_EXTERNAL = "read_external"
    WRITE_LOCAL = "write_local"
    WRITE_EXTERNAL = "write_external"
    DANGEROUS = "dangerous"

