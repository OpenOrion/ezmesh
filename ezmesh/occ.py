import cadquery as cq
from cadquery.cq import CQObject
from typing import Iterable, Literal, Optional, OrderedDict, Sequence, cast
from ezmesh.gmsh import DimType
from ezmesh.transactions.transaction import Entity

EntityType = Literal["solid", "shell", "face", "wire", "edge", "vertex"]

class OCCRegistry:
    def __init__(self, dim_type: DimType) -> None:
        self.dim_type = dim_type
        self.entities = OrderedDict[CQObject, Entity]()

class OCCMap:
    "Maps OCC objects to gmsh tags"
    def __init__(self, workplane: cq.Workplane) -> None:
        self.dimension = 2 if isinstance(workplane.val(), cq.Face) else 3

        self.registries: dict[EntityType, OCCRegistry] = {
            "solid": OCCRegistry(DimType.VOLUME),
            "shell": OCCRegistry(DimType.SURFACE_LOOP),
            "face":  OCCRegistry(DimType.SURFACE),
            "wire": OCCRegistry(DimType.CURVE_LOOP),
            "edge": OCCRegistry(DimType.CURVE),
            "vertex": OCCRegistry(DimType.POINT),
        }

        if self.dimension == 3:
            self._init_3d(workplane.vals())
        else:
            self._init_2d(workplane.vals())

    def _init_3d(self, objs: Sequence[CQObject]):
        for solid in cast(Sequence[cq.Solid], objs):
            for shell in solid.Shells():
                self._init_2d(shell.Faces())
                self.add_entity(shell)
            self.add_entity(solid)

    def _init_2d(self, objs: Sequence[CQObject]):
        for occ_face in cast(Sequence[cq.Face], objs):
            for occ_wire in [occ_face.outerWire(), *occ_face.innerWires()]:
                for occ_edge in occ_wire.Edges():
                    for occ_vertex in occ_edge.Vertices():
                        self.add_entity(occ_vertex)
                    self.add_entity(occ_edge)
                self.add_entity(occ_wire)
            self.add_entity(occ_face)

    def get_registry(self, shape: CQObject):
        if isinstance(shape, (cq.Compound, cq.Solid)): 
            return self.registries["solid"]
        if isinstance(shape, cq.Shell): 
            return self.registries["shell"]
        elif isinstance(shape, cq.Face):
            return self.registries["face"]
        elif isinstance(shape, cq.Wire):
            return self.registries["wire"]
        elif isinstance(shape, cq.Edge):
            return self.registries["edge"]
        elif isinstance(shape, cq.Vertex):
            return self.registries["vertex"]
        else:
            raise NotImplementedError(f"shape {shape} not supported")

    def add_entity(self, occ_obj: CQObject):
        registry = self.get_registry(occ_obj)
        if occ_obj not in registry.entities:
            tag = len(registry.entities) + 1
            registry.entities[occ_obj] = Entity(registry.dim_type, tag)

    def select_entity(self, occ_obj: CQObject, type: Optional[EntityType] = None):
        if type is None:
            registry = self.get_registry(occ_obj)
        else:
            registry = self.registries[type]
        return registry.entities[occ_obj]
    
    def select_entities(self, occ_objs: Iterable[CQObject], type: Optional[EntityType] = None):
        for occ_obj in occ_objs:
            try:
                yield self.select_entity(occ_obj, type)
            except:
                ...
