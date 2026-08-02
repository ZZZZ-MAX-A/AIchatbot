from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .database import database_path_scope


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PERSONA_MEMORY_DIR = PROJECT_ROOT / "data" / "persona-memory"
PERSONA_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def persona_database_path(persona_id: str) -> Path:
    normalized = persona_id.strip()
    if PERSONA_ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError("invalid persona id for database path")
    return PERSONA_MEMORY_DIR / f"{normalized}.db"


@contextmanager
def persona_memory_database_scope(persona_id: str) -> Iterator[None]:
    """Run the unchanged legacy memory stack against one persona DB file."""

    with database_path_scope(persona_database_path(persona_id)):
        yield
