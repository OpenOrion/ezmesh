import cadquery as cq
from cadquery.cq import CQObject
from typing import Iterable, Optional, OrderedDict, Sequence, Type, Union, cast
from ezmesh.transactions.transaction import DimType, Entity

class InteriorSelector(cq.Selector):
    def __init__(self, workplane: cq.Workplane, is_interior: bool = True):
        self.workplane = workplane
        self.is_interior = is_interior
    def filter(self, objectList):
        parent_objects = self.workplane.vals()
        if len(parent_objects) == 1 and isinstance(parent_objects[0], cq.Face): 
            return get_interior_edges(objectList[0], parent_objects[0], self.is_interior)
        return filter(lambda object: self.is_interior == get_interior_face(object), objectList)

def get_interior_face(object: cq.Face):
    face_normal = object.normalAt()
    face_centroid = object.Center()
    interior_dot_product = face_normal.dot(face_centroid)
    return interior_dot_product < 0

def get_interior_edges(object: Union[cq.Face, cq.Wire], parent: cq.Face, is_interior: bool):
    wires = parent.innerWires() if is_interior else [parent.outerWire()]
    if isinstance(object, cq.Wire): 
        return wires
    elif isinstance(object, cq.Edge):
        return [edge for  wire in wires for edge in wire.Edges()]

def get_selector(workplane: cq.Workplane, selector: Union[cq.Selector, str, None], is_interior: Optional[bool] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(cq.StringSyntaxSelector(selector))
    elif isinstance(selector, cq.Selector):
        selectors.append(selector)

    if is_interior is not None:
        selectors.append(InteriorSelector(workplane, is_interior))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = cq.selectors.AndSelector(prev_selector, selector)
        return prev_selector


def select_occ_type(workplane: cq.Workplane, type: Type):
    for val in workplane.vals():
        assert isinstance(val, cq.Shape), "target must be a shape"
        if isinstance(val, type):
            yield val
        elif type == cq.Face:
            yield from val.Faces()
        elif type == cq.Wire:
            yield from val.Wires()
        elif type == cq.Edge:
            yield from val.Edges()
        elif type == cq.Vertex:
            yield from val.Vertices()

def import_workplane(target: Union[cq.Workplane, str]):
    if isinstance(target, str):
        workplane = cq.importers.importStep(target)
    else:
        workplane = target
    if isinstance(workplane.val(), cq.Wire):
        workplane = workplane.extrude(-0.001).faces(">Z")

    return workplane

def tag_workplane(workplane: cq.Workplane, ctx: "OCCMap"):
    for name, registry in ctx.registries.items():
        for cq_object in registry.entities.keys():
            tag = f"{name}/{registry.entities[cq_object].tag}"
            workplane.newObject([cq_object]).tag(tag)

class OCCRegistry:
    def __init__(self, dim_type: DimType) -> None:
        self.dim_type = dim_type
        self.entities = OrderedDict[CQObject, Entity]()

class OCCMap:
    "Maps OCC objects to gmsh tags"
    def __init__(self, workplane: cq.Workplane) -> None:
        self.workplane = workplane
        self.dimension = 2 if isinstance(workplane.val(), cq.Face) else 3

        self.registries = {
            "volume": OCCRegistry(DimType.VOLUME),
            "surface_loop": OCCRegistry(DimType.SURFACE_LOOP),
            "surface":  OCCRegistry(DimType.SURFACE),
            "curve_loop": OCCRegistry(DimType.CURVE_LOOP),
            "curve": OCCRegistry(DimType.CURVE),
            "point": OCCRegistry(DimType.POINT),
        }

        if self.dimension == 3:
            solids = workplane.vals()
            for solid in  cast(Sequence[cq.Solid], solids):
                for shell in solid.Shells():
                    self._init_2d(shell.Faces())
                    self.add(shell)
                self.add(solid)
        else:
            self._init_2d(workplane.vals())

    def _init_2d(self, objs: Sequence[CQObject]):
        for occ_face in cast(Sequence[cq.Face], objs):
            for occ_wire in [occ_face.outerWire(), *occ_face.innerWires()]:
                for occ_edge in occ_wire.Edges():
                    for occ_vertex in occ_edge.Vertices():
                        self.add(occ_vertex)
                    self.add(occ_edge)
                self.add(occ_wire)
            self.add(occ_face)

    def get_registry(self, shape: CQObject):
        if isinstance(shape, (cq.Compound, cq.Solid)): 
            return self.registries["volume"]
        if isinstance(shape, cq.Shell): 
            return self.registries["surface_loop"]
        elif isinstance(shape, cq.Face):
            return self.registries["surface"]
        elif isinstance(shape, cq.Wire):
            return self.registries["curve_loop"]
        elif isinstance(shape, cq.Edge):
            return self.registries["curve"]
        elif isinstance(shape, cq.Vertex):
            return self.registries["point"]
        else:
            raise NotImplementedError(f"shape {shape} not supported")

    def add(self, occ_obj: CQObject):
        registry = self.get_registry(occ_obj)
        if occ_obj not in registry.entities:
            tag = len(registry.entities) + 1
            registry.entities[occ_obj] = Entity(registry.dim_type, tag)

    def select(self, shape: CQObject):
        registry = self.get_registry(shape)
        return registry.entities[shape]

    def select_many(self, shapes: Iterable[CQObject]):
        for cq_object in shapes:
            yield self.select(cq_object)
