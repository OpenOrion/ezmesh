from typing import Optional, Sequence, Type, Union
import cadquery as cq
import numpy as np
import gmsh
from ezmesh.geometry.transactions import Point, PlaneSurface, Volume
from ezmesh.geometry.transaction import DimType, Context
from cadquery import Selector
from cadquery.selectors import AndSelector, StringSyntaxSelector
from cadquery.cq import CQObject
from ezmesh.utils.norm import norm_coord

CQObject3D =  (cq.Compound, cq.Solid)

def unit_vec(vec: cq.Vector):
    return vec if vec == cq.Vector(0,0,0) else vec.normalized()

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

class InteriorSelector(Selector):
    def __init__(self, workplane: cq.Workplane, is_interior: bool = True):
        self.workplane = workplane
        self.is_interior = is_interior
    def filter(self, objectList):
        parent_objects = self.workplane.vals()
        if len(parent_objects) == 1 and isinstance(parent_objects[0], cq.Face): 
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


def get_cq_objects_as_type(workplane: cq.Workplane, type: Type):
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

def get_entity_id(target: CQObject):
    if isinstance(target, CQObject3D):
        type = DimType.VOLUME
    elif isinstance(target, cq.Face):
        type = DimType.SURFACE
    elif isinstance(target, cq.Wire):
        type = DimType.CURVE_LOOP
    elif isinstance(target, cq.Edge):
        type = DimType.CURVE
    elif isinstance(target, cq.Vertex):
        type = DimType.POINT
    else:
        raise ValueError(f"cannot get id for {target}")

    if isinstance(target, cq.Vertex):
        center_of_mass = norm_coord((target.X, target.Y, target.Z))
    elif isinstance(target, cq.Wire):
        raise NotImplementedError("cannot get center of mass for wire")
    else:
        center_of_mass =  norm_coord(target.centerOfMass(target).toTuple())
    return (type, center_of_mass)


def select_entities(cq_objects: Sequence[CQObject], ctx: Context):
    entities = []
    for cq_object in cq_objects:
        if isinstance(cq_object, cq.Wire):
            for edge in cq_object.Edges():
                id = get_entity_id(edge)
                entities.append(ctx.register[id])
        else:
            id = get_entity_id(cq_object)
            entities.append(ctx.register[id])
    return entities

def initialize_context(workplane: cq.Workplane, ctx: Context):
    topods = workplane.toOCC()
    
    gmsh.model.occ.importShapesNativePointer(topods._address())
    gmsh.model.occ.synchronize()
    gmsh.model.mesh.generate(1)

    for (_, point_tag) in gmsh.model.occ.getEntities(DimType.POINT.value):
        nodeTags, nodeCoords, nodeParams = gmsh.model.mesh.getNodes(DimType.POINT.value, point_tag)
        point = Point(nodeCoords, tag=point_tag) 
        ctx.add_point(point)
        ctx.register[point.id] = point

    surfaces: list[PlaneSurface] = []
    if ctx.dimension == 3:
        for (_, volume_tag) in gmsh.model.occ.getEntities(DimType.VOLUME.value):
            volume = Volume.from_tag(volume_tag, ctx)
            ctx.register[volume.id] = volume
            surfaces += volume.get_surfaces()
    else:
        for (_, surface_tag) in gmsh.model.occ.getEntities(DimType.SURFACE.value):
            surface = PlaneSurface.from_tag(surface_tag, ctx)
            surfaces.append(surface)

    for surface in surfaces:
        ctx.register[surface.id] = surface
        for edge in surface.get_edges():
                ctx.register[edge.id] = edge

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
