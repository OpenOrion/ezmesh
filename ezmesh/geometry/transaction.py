from dataclasses import field
import gmsh
import numpy as np
from typing import Iterable, Optional, Protocol, Sequence
from ezmesh.utils.types import DimType
from ezmesh.utils.types import Number, NumpyFloat

def normalize_coord(iterable: Iterable[Number], round_by: Optional[int] = 5) -> tuple[float, float, float]:
    return tuple(
        round(float(num), round_by) if round_by 
        else num
        for num in iterable # type: ignore
    )

GeoEntityId = tuple[DimType, tuple[float, float, float]]


def get_unique_edges(lst):
    unique_entries = set()

    for entry in lst:
        sorted_entry = tuple(sorted(entry))
        unique_entries.add(sorted_entry)

    return np.array([list(entry) for entry in unique_entries])

class MeshContext:
    point_tags: dict[tuple[Number, Number, Number], int]
    edge_tags: dict[tuple[int, int], int]
    points: dict[int, "GeoEntity"]
    edges: dict[int, "GeoEntity"]
    surfaces: dict[int, "GeoEntity"]
    register: dict[GeoEntityId, "GeoEntity"]
    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.point_tags = {}
        self.edge_tags = {}
        self.points = {}
        self.edges = {}
        self.surfaces = {}
        self.register = {}


    def add_surface(self, surface):
        self.surfaces[surface.tag] = surface

    def add_edge(self, edge):
        self.edges[edge.tag] = edge
        self.edge_tags[(edge.start.tag, edge.end.tag)] = edge.tag

    def add_point(self, point):
        self.point_tags[normalize_coord(point.coord, round_by=None)] = point.tag
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
        nodes_before_mesh =  gmsh.model.mesh.getNodes()
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


class GeoEntity(GeoTransaction, Protocol):
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

    def __eq__(self, __value: "GeoEntity") -> bool:
        return (self.type, self.tag) == (__value.type, __value.tag)