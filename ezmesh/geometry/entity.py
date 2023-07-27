import gmsh
import numpy as np
from enum import Enum
from typing import Optional, Protocol
from ezmesh.utils.types import NumpyFloat


class MeshContext:
    point_lookup: dict[tuple[float, float, float], int]
    point_registry: dict[int, "GeoEntity"]
    def __init__(self) -> None:
        self.point_lookup = {}

    def update(self):
        from ezmesh.geometry.point import Point

        gmsh.model.mesh.generate(1)
        point_entities = gmsh.model.occ.getEntities(0)

        node_tags, node_concatted, _ = gmsh.model.mesh.getNodes()
        point_tags = np.array([entity[1] for entity in point_entities], dtype=np.uint16)
        point_indices = np.argsort(point_tags-1)  # type: ignore
        point_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))[point_indices]

        for i, point_coord in enumerate(point_coords):
            self.point_lookup[tuple(point_coord)] = point_indices[i]+1

class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3


class GeoEntity(Protocol):
    tag: Optional[int] = None
    "tag of entity"

    def before_sync(self, ctx: MeshContext) -> int:
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        ...
