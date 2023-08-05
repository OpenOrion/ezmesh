from dataclasses import field
import gmsh
import numpy as np
from typing import Any, Callable, Iterable, Optional, Protocol, Sequence
from ezmesh.utils.types import DimType
from ezmesh.utils.types import Number, NumpyFloat

def format_coord_id(iterable: Iterable[Number], round_by: Optional[int] = 5):
    return tuple(round(float(num), round_by) if round_by else float(num)  for num in iterable)

GeoEntityId = tuple[DimType, tuple[float, float, float]]


class MeshContext:
    point_tags: dict[tuple[Number, Number, Number], int]
    points: dict[int, "GeoEntityTransaction"]
    edges: dict[int, "GeoEntityTransaction"]
    surfaces: dict[int, "GeoEntityTransaction"]

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.point_tags = {}
        self.points = {}
        self.edges = {}
        self.surfaces = {}
       
    def add_surface(self, surface):
        self.surfaces[surface.tag] = surface

    def add_edge(self, edge):
        self.edges[edge.tag] = edge

    def add_point(self, point):
        self.point_tags[format_coord_id(point.coord, round_by=None)] = point.tag
        self.points[point.tag] = point

    def get_physical_groups(self, type: DimType):
        if type == DimType.POINT:
            entities = self.points
        elif type == DimType.CURVE:
            entities = self.edges
        elif type == DimType.SURFACE:
            entities = self.surfaces
        else:
            raise ValueError(f"Invalid type: {type}")
        physical_groups: dict[str, list[int]] = {}
        for entity in entities.values():
            if not entity.label or not entity.tag:
                continue
            if entity.label not in physical_groups:
                physical_groups[entity.label] = []
            physical_groups[entity.label].append(entity.tag)
        return physical_groups

    def update(self):
        gmsh.model.mesh.generate(1)

        node_tags, node_concatted, _ = gmsh.model.mesh.getNodes()
        node_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))

        from ezmesh.geometry.point import Point
        for i, point_coord in enumerate(node_coords):
            self.add_point(Point(point_coord, tag=node_tags[i]))



class GeoTransaction(Protocol):
    def before_sync(self, ctx: MeshContext):
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        ...

class CommandTransaction(GeoTransaction):
    def __init__(self, before_sync: Callable[[MeshContext], None], after_sync: Callable[[MeshContext], None]):
        self.before_sync_func = before_sync
        self.after_sync_func = after_sync
    
    def before_sync(self, ctx: MeshContext):
        self.before_sync_func(ctx)

    def after_sync(self, ctx: MeshContext):
        self.after_sync_func(ctx)


class GeoEntityTransaction(GeoTransaction, Protocol):
    tag: Optional[int] = None
    "tag of entity"

    type: DimType
    "type of entity"

    label: Optional[str]
    "physical group label"        

    fields: Sequence = field(default_factory=list)
    "fields to be added to the surface"

    def before_sync(self, ctx: MeshContext) -> int:
        ...

    def set_label(self, label: str):
        self.label = label

    @property
    def id(self) -> GeoEntityId:
        vector_id = format_coord_id(gmsh.model.occ.getCenterOfMass(self.type.value, self.tag))
        return (self.type, vector_id)

    def __eq__(self, __value: "GeoEntityTransaction") -> bool:
        return (self.type, self.tag) == (__value.type, __value.tag)