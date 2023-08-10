from typing import Sequence, Type, Union, cast
import cadquery as cq
import numpy as np
import gmsh
from ezmesh.geometry.curve_loop import CurveLoop
from ezmesh.geometry.edge import Curve, Line
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.geometry.surface_loop import SurfaceLoop
from ezmesh.geometry.transaction import GeoEntity, MeshContext, format_coord_id
from ezmesh.geometry.volume import Volume
from cadquery import Face, Selector
from cadquery.selectors import AreaNthSelector, StringSyntaxSelector
from cadquery.cq import CQObject
from ezmesh.utils.geometry import commit_transactions
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

def get_selector(selector: Union[Selector, str, None] = None, index: int | None = None):
    assert not (index is not None and selector is not None), "cannot use both index and selector"
    if index is not None:
        selector = AreaNthSelector(index)    
    elif isinstance(selector, str):
        selector = StringSyntaxSelector(selector)

    return selector

def get_cq_objects_as_type(workplane: cq.Workplane, type: Type):
    vals = []
    for val in workplane.vals():
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

def get_entity_id(target: Union[CQObject, GeoEntity]):
    if isinstance(target, CQObject):
        if isinstance(target, (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid)):
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
            vector_id = format_coord_id((target.X, target.Y, target.Z))
        elif isinstance(target, cq.occ_impl.shapes.Wire):
            vector_id = format_coord_id(np.average([edge.centerOfMass(target).toTuple() for edge in target.Edges()], axis=0))
        else:
            vector_id =  format_coord_id(target.centerOfMass(target).toTuple())
        return (type, vector_id)
    else:
        if isinstance(target, Point):
            vector_id = format_coord_id(target.coord)
        else:
            vector_id = format_coord_id(gmsh.model.occ.getCenterOfMass(target.type.value, target.tag))
        return (target.type, vector_id)

def select_entities(workplane: cq.Workplane, ctx: MeshContext):
    entities = []
    for cq_object in workplane.vals():
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
    ctx: MeshContext,
    normalize: bool = False,
    mesh_size: float = 0.1,  
    samples_per_spline: int = 20
):
    surfaces: list[PlaneSurface] = []
    faces = target if isinstance(target, Sequence) else target.vals()

    for face in faces:
        curve_loops: list[CurveLoop] = []
        for wire in [face.outerWire(), *face.innerWires()]:
            edge_entities = []
            for edge in wire.Edges():
                first = edge.positionAt(0)
                middle = edge.positionAt(0.5)
                last = edge.positionAt(1) 

                is_line = norm(first - last) == norm(first - middle)
                if is_line:
                    edge_entity = Line(Point(first.toTuple(), mesh_size), Point(last.toTuple(), mesh_size))
                else:
                    points = [Point(vec.toTuple(), mesh_size) for vec in edge.positions(np.linspace(0, 1, samples_per_spline))]
                    edge_entity = Curve(points, "Spline")
                
                ctx.register[get_entity_id(edge)] = edge_entity
                for point in edge_entity.get_points():
                    if normalize:
                        point.z = 0
                    ctx.register[get_entity_id(point)] = point
                
                edge_entities.append(edge_entity)
            curve_loop = CurveLoop(edge_entities)
            curve_loops.append(curve_loop)
        surface = PlaneSurface(curve_loops)
        ctx.register[get_entity_id(face)] = surface
        surfaces.append(surface)
    return surfaces

def initialize_entities_3d(
    target: Union[cq.Workplane, Sequence[CQObject]],
    ctx: MeshContext,
    mesh_size: float = 0.1, 
    samples_per_spline: int = 20
):
    volumes = []
    solids = target if isinstance(target, Sequence) else target.vals()
    for solid in solids:
        surfaces = initialize_entities_2d(solid.Faces(), ctx, mesh_size, samples_per_spline)
        surface_loop = SurfaceLoop(surfaces)
        volume = Volume([surface_loop])
        ctx.register[get_entity_id(solid)] = volume
        volumes.append(volume)
    return volumes


def initialize_context(workplane: cq.Workplane):
    if isinstance(workplane.vals()[0], cq.occ_impl.shapes.Face):
        ctx = MeshContext(2)
        initialize_entities_2d(workplane, ctx, normalize=True)
    else:
        ctx = MeshContext(3)
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

def intialize_workplane(workplane: cq.Workplane, ctx: MeshContext):
    # Add all surfaces, edges and vertices to the workplane
    cq_objects = [
        *workplane.faces().vals(), 
        *workplane.edges().vals(), 
        *workplane.vertices().vals()
    ]
    for cq_object in cq_objects:
        dim_type, _ = id = get_entity_id(cq_object)
        tag = f"{dim_type.name.lower()}/{ctx.register[id].tag}"
        workplane.newObject([cq_object]).tag(tag)