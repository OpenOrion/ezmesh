from typing import Sequence, Type, Union
import cadquery as cq
import numpy as np
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Curve, Line
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.geometry.surface_loop import SurfaceLoop
from ezmesh.geometry.transaction import GeoEntityId, GeoEntityTransaction, format_coord_id
from ezmesh.geometry.volume import Volume
from cadquery import Face, Selector
from cadquery.selectors import AreaNthSelector, StringSyntaxSelector
from cadquery.cq import CQObject 
from ezmesh.utils.types import DimType

def is_interior_face(face: Face):
    # Get the normal of the face
    face_normal = face.normalAt()

    # Calculate the centroid of the face
    face_centroid = face.Center()

    # Calculate the dot product between the face normal and a vector from the centroid to an arbitrary point
    # inside the mesh (e.g., (0, 0, 0))
    interior_dot_product = face_normal.dot(face_centroid)

    return interior_dot_product < 0

def norm(vec: cq.Vector):
    if vec == cq.Vector(0,0,0):
        return vec
    return vec.normalized()

def get_cq_object_id(cqobject: CQObject):
    if isinstance(cqobject, (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid)):
        type = DimType.VOLUME
    elif isinstance(cqobject, cq.occ_impl.shapes.Face):
        type = DimType.SURFACE
    elif isinstance(cqobject, cq.occ_impl.shapes.Wire):
        type = DimType.CURVE_LOOP
    elif isinstance(cqobject, cq.occ_impl.shapes.Edge):
        type = DimType.CURVE
    elif isinstance(cqobject, cq.occ_impl.shapes.Vertex):
        type = DimType.POINT
    else:
        raise ValueError(f"cannot get id for {cqobject}")

    if isinstance(cqobject, cq.occ_impl.shapes.Vertex):
        vector_id = format_coord_id((cqobject.X, cqobject.Y, cqobject.Z))
    elif isinstance(cqobject, cq.occ_impl.shapes.Wire):
        vector_id = format_coord_id(np.average([edge.centerOfMass(cqobject).toTuple() for edge in cqobject.Edges()], axis=0))
    else:
        vector_id =  format_coord_id(cqobject.centerOfMass(cqobject).toTuple())
    return (type, vector_id)

def get_cq_objects(workspace: cq.Workplane, type: Type):
    vals = []
    for val in workspace.vals():
        if isinstance(val, (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid)):
            if type in (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid):
                vals.append(val)
            elif type == cq.occ_impl.shapes.Face:
                vals += val.Faces()
            elif type == cq.occ_impl.shapes.Edge:
                vals += val.Edges()
        else:
            assert isinstance(val, type), "non compound/solid tags must be of the same type as current workplane"
            vals.append(val)

    return vals

def get_entities(register: dict[GeoEntityId, GeoEntityTransaction], cq_objects: Sequence[CQObject]):
    entities = []
    for cq_object in cq_objects:
        if isinstance(cq_object, cq.occ_impl.shapes.Wire):
            for edge in cq_object.Edges():
                id = get_cq_object_id(edge)
                entities.append(register[id])
        else:
            id = get_cq_object_id(cq_object)
            entities.append(register[id])
    return entities

def get_selector(selector: Union[Selector, str, None] = None, index: int | None = None):
    assert not (index is not None and selector is not None), "cannot use both index and selector"
    
    if index is not None:
        selector = AreaNthSelector(index)    
    elif isinstance(selector, str):
        selector = StringSyntaxSelector(selector)

    return selector



def cq_workplane_to_volume(workplane: cq.Workplane, mesh_size: float = 0.1, samples_per_spline: int = 20):
    exterior_surfaces: list[PlaneSurface] = []
    interior_surfaces: list[PlaneSurface] = []

    for compound in workplane.vals():
        for face in compound.Faces():
            
            curve_loops: list[CurveLoop] = []
            for wire in [face.outerWire(), *face.innerWires()]:
                # face.facesIntersectedByLine
                edges = []
                for edge in wire.Edges():
                    first = edge.positionAt(0)
                    middle = edge.positionAt(0.5)
                    last = edge.positionAt(1) 

                    is_line = norm(first - last) == norm(first - middle)
                    if is_line:
                        edge = Line(Point(first.toTuple(), mesh_size), Point(last.toTuple(), mesh_size))
                    else:
                        points = [Point(vec.toTuple(), mesh_size) for vec in edge.positions(np.linspace(0, 1, samples_per_spline))]
                        edge = Curve(points, "Spline")
                    edges.append(edge)
                curve_loop = CurveLoop(edges)
                curve_loops.append(curve_loop)
            surface = PlaneSurface(curve_loops)
            # if is_interior_face(face):
            #     interior_surfaces.append(surface)
            # else:
            exterior_surfaces.append(surface)
    
    exterior_surface_loop = SurfaceLoop(exterior_surfaces)
    # interior_surface_loop = SurfaceLoop(interior_surfaces)

    return Volume([exterior_surface_loop])
