from dataclasses import field
import gmsh
from enum import Enum
from typing import Iterable, Optional, Sequence
import numpy as np
from ezmesh.utils.types import Number


class DimType(Enum):
    POINT = 0
    CURVE = 1
    SURFACE = 2
    VOLUME = 3
    CURVE_LOOP = 10
    

def norm_coord(iterable: Iterable[Number], round_by: Optional[int] = 5) -> tuple[float, float, float]:
    return tuple(
        round(float(num), round_by) if round_by 
        else num
        for num in iterable # type: ignore
    )

class GeoContext:
    def __init__(self, dimension: int) -> None:
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
    def __init__(self) -> None:
        self.is_synced: bool = False
        "whether geometry has been synced"

        self.is_commited: bool = False
        "whether geometry has been commited"

    def before_sync(self, ctx: GeoContext):
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: GeoContext):
        "completes transaction after syncronization and returns tag."
        ...


class GeoEntity(GeoTransaction):
    def __init__(self, type: DimType, tag: int = -1, label: Optional[str] = None) -> None:
        super().__init__()
        self.type = type
        "type of entity"

        # only set for non dataclasses that don't already have this defined
        if not hasattr(self, "tag"):
            self.tag = tag
            "tag of entity"

            self.label = label
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

    # def meshSizeCallback(dim, tag, x, y, z, lc=0.0):
    #     return min(lc, 0.02 * x + 0.01)

    # gmsh.model.mesh.setSizeCallback(meshSizeCallback)
    # gmsh.model.mesh.setSize([(0,5)], 0.01)
    # gmsh.model.mesh.setSize([(0,6)], 0.01)
    # gmsh.model.mesh.setSize([(0,7)], 0.01)
    # gmsh.model.mesh.setSize([(0,8)], 0.01)
    # gmsh.model.mesh.setSize([(0,9)], 0.01)
    # gmsh.model.mesh.setSize([(0,10)], 0.01)
    # gmsh.model.mesh.setSize([(0,11)], 0.01)
    # gmsh.model.mesh.setSize([(0,12)], 0.01)
    # gmsh.model.mesh.setSize([(0,13)], 0.01)

    # def meshSizeCallback(dim, tag, x, y, z):
    #     return 0.02 * x + 0.01
    # gmsh.model.mesh.setSizeCallback(meshSizeCallback)


    # gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
    # gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 1)
    # gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 1)
