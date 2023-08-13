from dataclasses import field
import gmsh
from enum import Enum
from typing import Optional, Sequence, cast
import numpy as np
from ezmesh.utils.norm import norm_coord
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import NumpyFloat


class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3
    CURVE_LOOP = 10
    


class GeoContext:
    points: dict[tuple[float, float, float], "GeoEntity"]
    curves: dict[tuple[tuple[float, float, float], tuple[float, float, float]], "GeoEntity"]

    def __init__(self, dimension) -> None:
        self.dimension = dimension
        self.points: dict[tuple[float, float, float], "GeoEntity"] = {}
        self.curves: dict[tuple[tuple[float, float, float], tuple[float, float, float]], "GeoEntity"] = {}
        self.physical_groups = {}

    def get_registry(self, entity: "GeoEntity"):
        if entity.type == DimType.POINT:
            self.points
        elif entity.type == DimType.CURVE:
            return self.curves
    
    def get_entity_id(self, entity: "GeoEntity"):
        if entity.type == DimType.POINT:
            return norm_coord(entity.coord, round_by=None) # type: ignore
        elif entity.type == DimType.CURVE:
            start_coord = norm_coord(entity.start.coord, round_by=None) # type: ignore
            end_coord = norm_coord(entity.end.coord, round_by=None) # type: ignore
            return (start_coord, end_coord)

    def add(self, entity: "GeoEntity"):
        entity_id = self.get_entity_id(entity)
        registry = self.get_registry(entity)
        registry[entity_id] = entity # type: ignore

    
    def get(self, entity: "GeoEntity"):
        registry = self.get_registry(entity)
        entity_id = self.get_entity_id(entity)
        return registry[entity_id] # type: ignore



class GeoTransaction:
    is_synced: bool = False
    "whether geometry has been synced"

    is_commited: bool = False
    "whether geometry has been commited"

    def before_sync(self, ctx: GeoContext):
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: GeoContext):
        "completes transaction after syncronization and returns tag."
        ...


class GeoEntity(GeoTransaction):
    tag: int
    "tag of entity"

    type: DimType
    "type of entity"

    label: Optional[str]
    "physical group label"        

    def set_label(self, label: str):
        self.label = label

    def __eq__(self, __value: "GeoEntity") -> bool:
        return (self.type, self.tag) == (__value.type, __value.tag)


def commit_geo_transactions(transactions: Sequence[GeoTransaction], ctx: GeoContext):
    for transaction in transactions:
        transaction.before_sync(ctx)
    gmsh.model.occ.synchronize()

    for transaction in transactions:
        transaction.after_sync(ctx)
        transaction.is_synced = True
        transaction.is_commited = True

