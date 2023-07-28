from dataclasses import field
import gmsh
import numpy as np
from enum import Enum
from typing import Optional, Protocol, Sequence
from ezmesh.utils.types import Number, NumpyFloat


class MeshContext:
    point_tags: dict[tuple[Number, Number, Number], int]
    
    def __init__(self) -> None:
        self.point_tags = {}

    def add_point(self, tag: int, coord: tuple[Number, Number, Number]):
        self.point_tags[coord] = tag

    def update(self):
        gmsh.model.mesh.generate(1)
        point_entities = gmsh.model.occ.getEntities(0)

        node_tags, node_concatted, _ = gmsh.model.mesh.getNodes()
        point_tags = np.array([entity[1] for entity in point_entities], dtype=np.uint16)
        point_indices = np.argsort(point_tags-1)  # type: ignore
        point_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))[point_indices]

        for i, point_coord in enumerate(point_coords):
            self.point_tags[tuple(point_coord)] = point_indices[i]+1

class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3


class GeoTransaction(Protocol):
    tag: Optional[int] = None
    "tag of entity"

    def before_sync(self, ctx: MeshContext) -> int:
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        ...

GeoEntityId = tuple[int, tuple[Number, Number, Number]]

class GeoEntity(GeoTransaction, Protocol):
    type: DimType
    "type of entity"

    label: Optional[str] = None
    "physical group label"        

    fields: Sequence = field(default_factory=list)
    "fields to be added to the surface"

    @property
    def center_of_mass(self):
        return tuple(round(x, 5) for x in gmsh.model.occ.getCenterOfMass(self.type.value, self.tag))

    @property
    def id(self) -> GeoEntityId:
        return (self.type.value, self.center_of_mass)