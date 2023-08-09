from typing import Callable, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
import gmsh
import cadquery as cq
from ezmesh.exporters import export_to_su2
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.utils.cadquery import get_cq_object_id, get_cq_objects, get_entities, get_selector
from ezmesh.utils.types import DimType
from ezmesh.geometry.transaction import GeoEntityTransaction, GeoEntityId, GeoTransaction, MeshContext
from ezmesh.geometry.field import ExtrudedBoundaryLayer, TransfiniteCurveField, TransfiniteSurfaceField, TransfiniteVolumeField
from ezmesh.geometry.plot import plot_entities
from ezmesh.geometry.volume import Volume
from ezmesh.mesh import Mesh
from ezmesh.utils.geometry import generate_mesh, commit_transactions
from jupyter_cadquery import show
from cadquery.selectors import InverseSelector

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
        self.mesh = generate_mesh([*transactions, *fields], self.ctx.dimension, self.ctx)
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
        self.initial_workplane = self.workplane
        self.file_path = target if isinstance(target, str) else "workplane.step"
        self.transactions = []
        self.mesh: Optional[Mesh] = None
        self.ctx = MeshContext()
        self.register: dict[GeoEntityId, GeoEntityTransaction] = {}
        self.update()

    def update(self):

        gmsh.initialize()
        if not isinstance(self.target, str) and self.file_path.endswith(".step"):
            cq.exporters.export(self.workplane, self.file_path)

        gmsh.open(self.file_path)
        gmsh.model.geo.synchronize()

        self.ctx.update() 
        for (_, volume_tag) in gmsh.model.occ.getEntities(DimType.VOLUME.value):
            volume = Volume.from_tag(volume_tag, self.ctx)
            self.register[volume.id] = volume
            for surface_loop in volume.surface_loops:
                for surface in surface_loop.surfaces:
                    self.register[surface.id] = surface
                    for curve_loop in surface.curve_loops:
                        # self.register[curve_loop.id] = curve_loop
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
        self.workplane = self.initial_workplane

    def filter(self, selector: Union[Selector, str, None] = None, tags:Union[Sequence[str], str, None]= None, inverse=False):
        tags = [tags ]if isinstance(tags, str) else tags or []
        cq_objects = self.workplane.vals()
        filtered_cq_objects = []

        selector = get_selector(selector)
        if inverse and selector:
            selector = InverseSelector(selector)
            cq_objects = selector.filter(cq_objects)
        elif not inverse and selector:
            filtered_cq_objects += selector.filter(cq_objects)

        tagged_cq_objects = []
        for tag in tags:
            tagged_workspace = self.workplane._getTagged(tag)
            tagged_cq_objects += get_cq_objects(tagged_workspace, type(cq_objects[0]))
        tagged_cq_object_ids = [get_cq_object_id(tagged_cq_object) for tagged_cq_object in tagged_cq_objects] 

        for cq_object in cq_objects:
            id = get_cq_object_id(cq_object)
            if (not inverse and id in tagged_cq_object_ids) or (inverse and id not in tagged_cq_object_ids):
                filtered_cq_objects.append(cq_object)

        self.workplane = self.workplane.newObject(filtered_cq_objects)
        return self


    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, index: int | None = None):
        selector = get_selector(selector, index)
        self.workplane = self.workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, index: int | None = None):
        selector = get_selector(selector, index)
        self.workplane = self.workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, index: int | None = None):
        selector = get_selector(selector, index)
        self.workplane = self.workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None, index: int | None = None):
        selector = get_selector(selector, index)
        self.workplane = self.workplane.vertices(selector, tag)
        return self

    def vals(self) -> Sequence[GeoEntityTransaction]:
        return get_entities(self.register, self.workplane.vals())

    def tag(self, name: str):
        self.workplane = self.workplane.tag(name)
        return self

    def fromTagged(self, name: str):
        self.workplane = self.workplane._getTagged(name)
        self.level = 0
        return self

    def addPhysicalGroup(self, name: str, tagWorkspace: bool = True):
        for entity in self.vals():
            entity.set_label(name)
        if tagWorkspace:
            self.tag(name)
        self.reset()
        return self

    def addTransfiniteVolume(self):
        for volume in cast(Sequence[Volume], self.vals()):
            volume_field = TransfiniteVolumeField([volume])
            self.transactions.append(volume_field)
        self.reset()
        return self

    def addTransfiniteSurface(self, node_count: int, point_select: Callable[[cq.Workplane], cq.Workplane]):
        surfaces = cast(Sequence[PlaneSurface], self.vals())
        for surface in surfaces:
            edges = surface.get_edges()
            curve_field = TransfiniteCurveField(edges, [node_count]*len(edges))
            points = get_entities(self.register, point_select(self.workplane).vals())
            surface_field = TransfiniteSurfaceField(surface, points)
            self.transactions.append(curve_field)
            self.transactions.append(surface_field)
        self.reset()
        return self
    

    def setSurfaceQuads(self, quads: bool = True):
        for surface in cast(Sequence[PlaneSurface], self.vals()):
            surface.set_quad(quads)
        self.reset()
        return self

    def setMeshSizes(self, mesh_size: Union[float, Callable[[Point], float]]):
        for point in cast(Sequence[Point], self.vals()):
            if isinstance(mesh_size, Callable):
                mesh_size = mesh_size(point)
            point.set_mesh_size(mesh_size)
        self.reset()
        return self

    def addTransfiniteSurfaceField(self):
        surfaces = cast(Sequence[PlaneSurface], self.vals())
        surface_field = TransfiniteSurfaceField(surfaces)
        self.transactions.append(surface_field)
        return self


    def addBoundaryLayer(self, num_layers: int, hwall_n: float, ratio: float):
        target = cast(Sequence[Union[PlaneSurface, Edge]], self.vals())
        ext_bnd_layer = ExtrudedBoundaryLayer(target, num_layers, hwall_n, ratio)
        self.transactions.append(ext_bnd_layer)
        self.reset()
        return self

    def to_mesh(self, dim: int = 3):
        mesh = generate_mesh([*self.vals(), *self.transactions], dim, self.ctx)
        self.reset()
        return mesh

    def write(self, filename: str, dim: int = 3):
        mesh = self.to_mesh(dim)
        if filename.endswith(".su2"):
            export_to_su2(mesh, filename)
        else:
            gmsh.write(filename)
        return self

    def show(self):
        show(self.workplane)
        return self

    def plot(self, include_surfaces=True, include_edges=True, include_points=False, title: str = "Plot", samples_per_spline: int = 20, ):
        entities = self.vals()
        plot_entities(entities, include_surfaces, include_edges, include_points, title, samples_per_spline)
        return self

    def close(self):
        gmsh.finalize()
