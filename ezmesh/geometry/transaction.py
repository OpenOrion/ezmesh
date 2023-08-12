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
    register: dict[GeoEntityId, "GeoEntity"]
    point_tags: dict[tuple[Number, Number, Number], int]
    edge_tags: dict[tuple[int, int], int]

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.point_tags = {}
        self.edge_tags = {}
        self.register = {}

    def add_edge(self, edge):
        self.edge_tags[(edge.start.tag, edge.end.tag)] = edge.tag

    def add_point(self, point):
        self.point_tags[norm_coord(point.coord)] = point.tag



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
    # for point in ctx.points.values():
    #     point.before_sync(ctx)    
    gmsh.model.occ.synchronize()

    for transaction in transactions:
        transaction.after_sync(ctx)
        transaction.is_commited = True
    # for point in ctx.points.values():
    #     point.after_sync(ctx)

