from typing import Optional, OrderedDict, Sequence, Type, Union, cast
import cadquery as cq
import gmsh
from ezmesh.geometry.transactions import Point, PlaneSurface, Volume, Curve, CurveLoop, SurfaceLoop
from ezmesh.geometry.transaction import GeoEntity
from cadquery import Selector
from cadquery.selectors import AndSelector, StringSyntaxSelector
from ezmesh.geometry.transactions.curve_loop import CurveLoop
from cadquery.cq import CQObject

class OCPContext:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self.volumes: OrderedDict[CQObject, GeoEntity] = OrderedDict()
        self.surface_loops: OrderedDict[CQObject, GeoEntity] = OrderedDict()

        self.surfaces: OrderedDict[CQObject, GeoEntity] = OrderedDict()
        self.curve_loops: OrderedDict[CQObject, GeoEntity] = OrderedDict()
        self.edges: OrderedDict[CQObject, GeoEntity] = OrderedDict()
        self.points: OrderedDict[CQObject, GeoEntity] = OrderedDict()

    def get_registry(self, shape: CQObject)-> OrderedDict[CQObject, GeoEntity]:
        if isinstance(shape, (cq.Compound, cq.Solid)): 
            return self.volumes
        if isinstance(shape, cq.Shell): 
            return self.surface_loops
        elif isinstance(shape, cq.Face):
            return self.surfaces
        elif isinstance(shape, cq.Wire):
            return self.curve_loops
        elif isinstance(shape, cq.Edge):
            return self.edges
        elif isinstance(shape, cq.Vertex):
            return self.points
        else:
            raise NotImplementedError(f"shape {shape} not supported")

    def add(self, shape: CQObject, child_shapes: Sequence[CQObject] = []):
        child_entities = list(self.select_many(child_shapes)) if not isinstance(shape, cq.Vertex) else []
        registry = self.get_registry(shape)
        if shape not in registry:
            next_tag = len(registry) + 1
            if isinstance(shape, (cq.Compound, cq.Solid)): 
                registry[shape] = Volume(cast(Sequence[SurfaceLoop], child_entities), tag=next_tag)
            if isinstance(shape, cq.Shell): 
                registry[shape] = SurfaceLoop(cast(Sequence[PlaneSurface], child_entities), tag=next_tag)
            elif isinstance(shape, cq.Face):
                registry[shape] = PlaneSurface(cast(Sequence[CurveLoop], child_entities), tag=next_tag)
            elif isinstance(shape, cq.Wire):
                registry[shape] = CurveLoop(cast(Sequence[Curve], child_entities), tag=next_tag)
            elif isinstance(shape, cq.Edge):
                curve_type = shape.geomType()
                radii = [shape.radius()] if curve_type in ("CIRCLE", "ELLIPSE") else None
                registry[shape] = Curve(cast(Sequence[Point], child_entities), curve_type, radii, tag=next_tag)
            elif isinstance(shape, cq.Vertex):
                registry[shape] = Point((shape.X, shape.Y, shape.Z), tag=next_tag)
            registry[shape].is_synced = True
    def select(self, shape: CQObject):
        registry = self.get_registry(shape)
        return registry[shape]

    def select_many(self, shapes: Sequence[CQObject]):
        for cq_object in shapes:
            yield self.select(cq_object)      

class InteriorSelector(Selector):
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


def get_selector(workplane: cq.Workplane, selector: Union[Selector, str, None], is_interior: Optional[bool] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(StringSyntaxSelector(selector))
    elif isinstance(selector, Selector):
        selectors.append(selector)

    if is_interior is not None:
        selectors.append(InteriorSelector(workplane, is_interior))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = AndSelector(prev_selector, selector)
        return prev_selector


def select_ocp_type(workplane: cq.Workplane, type: Type):
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

def initialize_gmsh_from_cq(workplane: cq.Workplane):
    topods = workplane.toOCC()
    gmsh.model.occ.importShapesNativePointer(topods._address())
    gmsh.model.occ.synchronize()


def initialize_context_2d(target: Union[cq.Workplane, Sequence[CQObject]], ctx: OCPContext):
    ocp_faces = target if isinstance(target, Sequence) else target.vals()
    for ocp_face in cast(Sequence[cq.Face], ocp_faces):
        cq_wires = [ocp_face.outerWire(), *ocp_face.innerWires()]
        for ocp_wire in cq_wires:
            ocp_edges = ocp_wire.Edges()
            for ocp_edge in ocp_edges:
                ocp_vertices = ocp_edge.Vertices()
                for ocp_vertex in ocp_vertices:
                    ctx.add(ocp_vertex)
                ctx.add(ocp_edge, ocp_vertices)
            ctx.add(ocp_wire, ocp_edges)
        ctx.add(ocp_face, cq_wires)



def initialize_context(workplane: cq.Workplane, ctx: OCPContext):
    if ctx.dimension == 3:
        solids = workplane.vals()
        for solid in  cast(Sequence[cq.Solid], solids):
            ocp_shells = solid.Shells()
            for shell in cast(Sequence[cq.Shell],ocp_shells):
                ocp_faces = shell.Faces()
                initialize_context_2d(ocp_faces, ctx)
                ctx.add(shell, ocp_faces)
            ctx.add(solid, ocp_shells)
    else:
        initialize_context_2d(workplane, ctx)
    return ctx

def intialize_workplane(workplane: cq.Workplane, ctx: OCPContext):

    cq_objects = [
        *workplane.faces().vals(), 
        *workplane.edges().vals(), 
        *workplane.vertices().vals()
    ]
    entities = ctx.select_many(cq_objects)
    for i, entity in enumerate(entities):
        assert entity is not None
        tag = f"{entity.type.name.lower()}/{entity.tag}"
        workplane.newObject([cq_objects[i]]).tag(tag)
