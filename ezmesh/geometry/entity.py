from enum import Enum
from typing import Optional, Protocol

class MeshContext:
    point_registry: dict[tuple[float, float, float], int]
    line_registry: dict[tuple[int, int], int]

    def __init__(self) -> None:
        self.point_registry = {}
        self.line_registry = {}

class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3


class GeoEntity(Protocol):
    tag: Optional[int]
    "tag of entity"

    def before_sync(self, ctx: MeshContext) -> int:
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        ...
