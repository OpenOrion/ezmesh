from typing import Callable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
import gmsh
import cadquery as cq
import numpy as np
from ezmesh.exporters import export_to_su2
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.utils.types import DimType
from ezmesh.geometry.transaction import GeoEntityTransaction, GeoEntityId, GeoTransaction, MeshContext, format_coord_id
from ezmesh.geometry.field import BoundaryLayerField, TransfiniteCurveField, TransfiniteSurfaceField
from ezmesh.geometry.plot import plot_entities
from ezmesh.geometry.volume import Volume
from ezmesh.mesh import Mesh
from ezmesh.utils.geometry import PropertyType, generate_mesh, commit_transactions
from jupyter_cadquery import show

def get_cq_object_id(cqobject):
    if isinstance(cqobject, (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid)):
        type = DimType.VOLUME
    elif isinstance(cqobject, cq.occ_impl.shapes.Face):
        type = DimType.SURFACE
    elif isinstance(cqobject, cq.occ_impl.shapes.Edge):
        type = DimType.CURVE
    elif isinstance(cqobject, cq.occ_impl.shapes.Vertex):
        type = DimType.POINT
    else:
        raise ValueError(f"cannot get id for {cqobject}")

    if isinstance(cqobject, cq.occ_impl.shapes.Vertex):
        center_of_mass = format_coord_id((cqobject.X, cqobject.Y, cqobject.Z))
    else:
        center_of_mass =  format_coord_id(cqobject.centerOfMass(cqobject).toTuple())
    return (type, center_of_mass)

class Geometry:
    def __init__(self) -> None:
        self.ctx = MeshContext()

    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def commit(self, transactions: Union[GeoTransaction, Sequence[GeoTransaction]]):
        commit_transactions(transactions, self.ctx)

    def generate(self, transactions: Union[GeoTransaction, Sequence[GeoTransaction]], fields: Optional[Sequence[GeoTransaction]] = None):
        fields = fields if fields is not None else []
        transactions = transactions if isinstance(transactions, Sequence) else [transactions]
        if isinstance(transactions, Sequence) and isinstance(transactions[0], PlaneSurface):
            self.ctx.dimension = 2
        else:
            self.ctx.dimension = 3
        self.mesh = generate_mesh([*transactions, *fields], self.ctx)
        return self.mesh

    def write(self, filename: str):
        if filename.endswith(".su2"):
            export_to_su2(self.mesh, filename)
        else:
            gmsh.write(filename)


class GeometryQL:
    def __init__(self, target: Union[cq.Workplane, str]) -> None:
        self.target = target
        self.workplane = cq.importers.importStep(target) if isinstance(target, str) else target
        self.file_path = target if isinstance(target, str) else "workplane.step"
        self.transactions = []
        self.fields = []
        self.mesh: Optional[Mesh] = None
        self.ctx = MeshContext()
        self.register: dict[GeoEntityId, GeoEntityTransaction] = {}
        self.update()

    def update(self):
        self.workplane.tag("root")

        gmsh.initialize()
        if not isinstance(self.target, str) and self.file_path.endswith(".step"):
            cq.exporters.export(self.workplane, self.file_path)

        gmsh.open(self.file_path)
        gmsh.model.geo.synchronize()

        self.ctx.update() 
        for (_, volume_tag) in gmsh.model.occ.getEntities(DimType.VOLUME.value):
            volume = Volume.from_tag(volume_tag, self.ctx)
            self.transactions.append(volume)
            self.register[volume.id] = volume
            for surface_loop in volume.surface_loops:
                for surface in surface_loop.surfaces:
                    self.register[surface.id] = surface
                    for curve_loop in surface.curve_loops:
                        for edge in curve_loop.edges:
                            self.register[edge.id] = edge
        
        for tag, point in self.ctx.points.items():
            self.register[point.id] = point

        # Add all surfaces, edges and vertices to the workplane
        cq_objects = [
            *self.workplane.faces().vals(), 
            *self.workplane.edges().vals(), 
            *self.workplane.vertices().vals()
        ]
        for cq_object in cq_objects:
            dim_type, _ = id = get_cq_object_id(cq_object)
            tag = f"{dim_type.name.lower()}/{self.register[id].tag}"
            self.workplane.newObject([cq_object]).tag(tag)

    def reset(self):
        self.workplane = self.workplane._getTagged("root")

    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None):
        self.workplane = self.workplane.vertices(selector, tag)
        return self

    def vals(self) -> Sequence[GeoEntityTransaction]:
        entities = []
        for cq_val_object in self.workplane.vals():
            # accounting for Wire objects that have multiple edges in on object
            cqobjects = (cq_val_object,)
            for cqobject in cqobjects:
                id = get_cq_object_id(cqobject)
                entities.append(self.register[id])
        return entities

    def tag(self, name: str):
        self.workplane = self.workplane.tag(name)
        return self

    def fromTagged(self, name: str):
        self.workplane = self.workplane._getTagged(name)
        self.level = 0
        return self

    def addPhysicalGroup(self, name: str, tagWorkspace: bool = True):
        for entity in self.vals():
            entity.label = name
        if tagWorkspace:
            self.tag(name)
        self.reset()
        return self

    # def addTransfiniteCurveField(self, node_counts: PropertyType[int], mesh_types: Optional[PropertyType[str]] = None, coefs: Optional[PropertyType[float]] = None):
    #     for entity in self.vals():
    #         assert isinstance(entity, PlaneSurface), "field entity must be a PlaneSurface"
    #         curve_field = TransfiniteCurveField(node_counts, mesh_types, coefs)

    # def addTransfiniteSurfaceField(self):
    #     for entity in self.vals():
    #         assert isinstance(entity, PlaneSurface), "field entity must be a PlaneSurface"
    #         edges = self.workplane.edges().vals()
    #         surface_field = TransfiniteSurfaceField(points)
    #         entity.add_field(surface_field)

    def addBoundaryLayerField(self, aniso_max: float | None = None, hfar: float | None = None, hwall_n: float | None = None, ratio: float | None = None, thickness: float | None = None, intersect_metrics: bool = False, is_quad_mesh: bool = False):
        edges = cast(Sequence[Edge], self.vals()) 
        field = BoundaryLayerField(edges, aniso_max, hfar, hwall_n, ratio, thickness, intersect_metrics, is_quad_mesh)
        self.fields.append(field)
        self.reset()
        return self

    def to_mesh(self, dim: int = 3):
        mesh = generate_mesh(self.vals(), self.ctx, dim)
        self.reset()
        return mesh

    def write(self, filename: str):
        mesh = self.to_mesh()
        if filename.endswith(".su2"):
            export_to_su2(mesh, filename)
        else:
            gmsh.write(filename)
        return self

    def show(self):
        show(self.workplane)
        return self

    def plot(self):
        entities = self.vals()
        plot_entities(entities)
        return self

    def close(self):
        gmsh.finalize()
