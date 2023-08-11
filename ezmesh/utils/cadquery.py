from typing import Optional, Sequence, Type, Union
import cadquery as cq
import numpy as np
import gmsh
from ezmesh.geometry.transactions import Point, Curve, Line, CurveLoop, PlaneSurface, SurfaceLoop, Volume
from ezmesh.geometry.transaction import DimType, GeoEntity, Context
from cadquery import Selector
from cadquery.selectors import AndSelector, StringSyntaxSelector
from cadquery.cq import CQObject
from ezmesh.utils.geometry import normalize_coord

CQObject3D =  (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid)
CQObject2D =  (cq.occ_impl.shapes.Face, cq.occ_impl.shapes.Wire)

def get_interior_face(object: cq.occ_impl.shapes.Face):
    face_normal = object.normalAt()
    face_centroid = object.Center()
    interior_dot_product = face_normal.dot(face_centroid)
    return interior_dot_product < 0

def get_interior_edges(
    object: Union[cq.occ_impl.shapes.Face, cq.occ_impl.shapes.Wire], 
    parent_object: cq.occ_impl.shapes.Face,
    is_interior: bool
):
    wires = parent_object.innerWires() if is_interior else [parent_object.outerWire()]
    if isinstance(object, cq.occ_impl.shapes.Wire): 
        return wires
    elif isinstance(object, cq.occ_impl.shapes.Edge):
        return [edge for  wire in wires for edge in wire.Edges()]

class InteriorSelector(Selector):
    def __init__(self, workplane: cq.Workplane, is_interior: bool = True):
        self.workplane = workplane
        self.is_interior = is_interior
    def filter(self, objectList):
        parent_objects = self.workplane.vals()
        if len(parent_objects) == 1 and isinstance(parent_objects[0], cq.occ_impl.shapes.Face): 
            return get_interior_edges(objectList[0], parent_objects[0], self.is_interior)
        return filter(lambda object: self.is_interior == get_interior_face(object), objectList)

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

def norm(vec: cq.Vector):
    if vec == cq.Vector(0,0,0):
        return vec
    return vec.normalized()

def get_cq_objects_as_type(workplane: cq.Workplane, type: Type):
    vals = []
    for val in workplane.vals():
        if isinstance(val, type):
            vals.append(val)
        elif type == cq.occ_impl.shapes.Face:
            vals += val.Faces()
        elif type == cq.occ_impl.shapes.Wire:
            vals += val.Wires()
        elif type == cq.occ_impl.shapes.Edge:
            vals += val.Edges()
        elif type == cq.occ_impl.shapes.Vertex:
            vals += val.Vertices()

    return vals

def get_entity_id(target: Union[CQObject, GeoEntity]):
    if isinstance(target, CQObject):
        if isinstance(target, CQObject3D):
            type = DimType.VOLUME
        elif isinstance(target, cq.occ_impl.shapes.Face):
            type = DimType.SURFACE
        elif isinstance(target, cq.occ_impl.shapes.Wire):
            type = DimType.CURVE_LOOP
        elif isinstance(target, cq.occ_impl.shapes.Edge):
            type = DimType.CURVE
        elif isinstance(target, cq.occ_impl.shapes.Vertex):
            type = DimType.POINT
        else:
            raise ValueError(f"cannot get id for {target}")

        if isinstance(target, cq.occ_impl.shapes.Vertex):
            vector_id = normalize_coord((target.X, target.Y, target.Z))
        elif isinstance(target, cq.occ_impl.shapes.Wire):
            vector_id = normalize_coord(np.average([edge.centerOfMass(target).toTuple() for edge in target.Edges()], axis=0))
        else:
            vector_id =  normalize_coord(target.centerOfMass(target).toTuple())
        return (type, vector_id)
    else:
        if isinstance(target, Point):
            vector_id = normalize_coord(target.coord)
        else:
            vector_id = normalize_coord(gmsh.model.occ.getCenterOfMass(target.type.value, target.tag))
        return (target.type, vector_id)

def select_entities(cq_objects: Sequence[CQObject], ctx: Context):
    entities = []
    for cq_object in cq_objects:
        if isinstance(cq_object, cq.occ_impl.shapes.Wire):
            for edge in cq_object.Edges():
                id = get_entity_id(edge)
                entities.append(ctx.register[id])
        else:
            id = get_entity_id(cq_object)
            entities.append(ctx.register[id])
    return entities

def initialize_entities_2d(
    target: Union[cq.Workplane, Sequence[CQObject]],
    ctx: Context,
    mesh_size: float = 0,  
    samples_per_spline: int = 20
):
    surfaces: list[PlaneSurface] = []
    faces = target if isinstance(target, Sequence) else target.vals()

    for face in faces:
        assert isinstance(face, cq.occ_impl.shapes.Face), "target must be a face"
        curve_loops: list[CurveLoop] = []
        for wire in [face.outerWire(), *face.innerWires()]:
            edge_entities = []
            for edge in wire.Edges():
                first = edge.positionAt(0)
                middle = edge.positionAt(0.5)
                last = edge.positionAt(1) 

                is_line = norm(first - last) == norm(first - middle)
                if is_line:
                    line = Line(Point(normalize_coord(first.toTuple()), mesh_size), Point(normalize_coord(last.toTuple()), mesh_size))
                else:
                    edges_points = edge.positions(np.linspace(0, 1, samples_per_spline, endpoint=True))
                    points = [Point(normalize_coord(vec.toTuple()), mesh_size) for vec in edges_points]
                    points.append(points[0])
                    line = Curve(points, "Spline")
                
                ctx.register[get_entity_id(edge)] = line
                for point in line.get_points():
                    point_id = get_entity_id(point)
                    ctx.register[point_id] = point
                
                    edge_entities.append(line)
                curve_loop = CurveLoop(edge_entities)
                curve_loops.append(curve_loop)
        surface = PlaneSurface(curve_loops)
        ctx.register[get_entity_id(face)] = surface
        surfaces.append(surface)
    return surfaces

def initialize_entities_3d(
    target: Union[cq.Workplane, Sequence[CQObject]],
    ctx: Context,
    mesh_size: float = 0.1, 
    samples_per_spline: int = 20
):
    volumes = []
    solids = target if isinstance(target, Sequence) else target.vals()
    for solid in solids:
        assert isinstance(solid, CQObject3D), "target must be a solid or compound"
        surfaces = initialize_entities_2d(solid.Faces(), ctx, mesh_size, samples_per_spline)
        surface_loop = SurfaceLoop(surfaces)
        volume = Volume([surface_loop])
        ctx.register[get_entity_id(solid)] = volume
        volumes.append(volume)
    return volumes


def initialize_context(workplane: cq.Workplane, ctx: Context):
    if ctx.dimension == 2:
        initialize_entities_2d(workplane, ctx)
    else:
        file_path = "workplane.step"
        cq.exporters.export(workplane, file_path)

        gmsh.open(file_path)
        gmsh.model.geo.synchronize()

        for (_, volume_tag) in gmsh.model.occ.getEntities(DimType.VOLUME.value):
            volume = Volume.from_tag(volume_tag, ctx)
            ctx.register[get_entity_id(volume)] = volume
            for surface in volume.get_surfaces():
                ctx.register[get_entity_id(surface)] = surface
                for edge in surface.get_edges():
                        ctx.register[get_entity_id(edge)] = edge
                        for point in edge.get_points():
                            ctx.register[get_entity_id(point)] = point

        for point in ctx.points.values():
            ctx.register[get_entity_id(point)] = point
    return ctx

def intialize_workplane(workplane: cq.Workplane, ctx: Context):

    cq_objects = [
        *workplane.faces().vals(), 
        *workplane.edges().vals(), 
        *workplane.vertices().vals()
    ]
    for cq_object in cq_objects:
        dim_type, _ = id = get_entity_id(cq_object)
        tag = f"{dim_type.name.lower()}/{ctx.register[id].tag}"
        workplane.newObject([cq_object]).tag(tag)
