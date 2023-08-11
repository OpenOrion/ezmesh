from dataclasses import field
import gmsh
from enum import Enum
from typing import Optional, Sequence
import numpy as np
from ezmesh.utils.norm import norm_coord
from ezmesh.utils.types import Number, NumpyFloat


class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3
    CURVE_LOOP = 10
    
GeoEntityId = tuple[DimType, tuple[float, float, float]]


class Context:
    point_tags: dict[tuple[Number, Number, Number], int]
    edge_tags: dict[tuple[int, int], int]
    points: dict[int, "GeoEntity"]
    edges: dict[int, "GeoEntity"]
    surfaces: dict[int, "GeoEntity"]
    volumes: dict[int, "GeoEntity"]
    register: dict[GeoEntityId, "GeoEntity"]
    physical_groups: dict[tuple[DimType, str], int]

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.point_tags = {}
        self.edge_tags = {}
        self.points = {}
        self.edges = {}
        self.surfaces = {}
        self.volumes = {}
        self.register = {}
        self.physical_groups = {}

    def add_physical_group(self, type: DimType, tag: int, label: str):
        self.physical_groups[(type, label)] = tag

    def add_volume(self, volume):
        self.volumes[volume.tag] = volume

    def add_surface(self, surface):
        self.surfaces[surface.tag] = surface

    def add_edge(self, edge):
        self.edges[edge.tag] = edge
        self.edge_tags[(edge.start.tag, edge.end.tag)] = edge.tag

    def add_point(self, point):
        self.point_tags[norm_coord(point.coord, round_by=None)] = point.tag
        self.points[point.tag] = point

    def get_label_groups(self, type: DimType):
        if type == DimType.POINT:
            entities = self.points
        elif type == DimType.CURVE:
            entities = self.edges
        elif type == DimType.SURFACE:
            entities = self.surfaces
        else:
            raise ValueError(f"Invalid type: {type}")
        physical_groups: dict[str, list[GeoEntity]] = {}
        for entity in entities.values():
            if not entity.label or not entity.tag:
                continue
            if entity.label not in physical_groups:
                physical_groups[entity.label] = []
            physical_groups[entity.label].append(entity)
        return physical_groups

    def update(self):
        gmsh.model.mesh.generate(1)

        node_tags, node_concatted, _ = gmsh.model.mesh.getNodes()
        node_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))

        from ezmesh.geometry.transactions.point import Point
        for i, point_coord in enumerate(node_coords):
            point = Point(point_coord, tag=node_tags[i])
            self.add_point(point)
            self.register[point.id] = point
        


class GeoTransaction:
    is_commited: bool = False
    "tag of entity"

    def before_sync(self, ctx: Context):
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: Context):
        "completes transaction after syncronization and returns tag."
        ...


class GeoEntity(GeoTransaction):
    tag: Optional[int] = None
    "tag of entity"

    type: DimType
    "type of entity"

    label: Optional[str]
    "physical group label"        

    fields: Sequence = field(default_factory=list)
    "fields to be added to the surface"

    def set_label(self, label: str):
        self.label = label

    def __eq__(self, __value: "GeoEntity") -> bool:
        return (self.type, self.tag) == (__value.type, __value.tag)
    
    @property
    def id(self) -> GeoEntityId:
        return (self.type, norm_coord(gmsh.model.occ.getCenterOfMass(self.type.value, self.tag)))


def commit_geo_transactions(transactions: Sequence[GeoTransaction], ctx: Context):
    for transaction in transactions:
        transaction.before_sync(ctx)
    gmsh.model.geo.synchronize()
    for transaction in transactions:
        transaction.after_sync(ctx)
        transaction.is_commited = True