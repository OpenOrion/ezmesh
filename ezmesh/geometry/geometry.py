from typing import Callable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
import gmsh
import cadquery as cq
from ezmesh.exporters import export_to_su2
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.plane_surface import PlaneSurface
from ezmesh.geometry.point import Point
from ezmesh.utils.cadquery import get_entity_id, get_cq_objects_as_type, select_entities, get_selector, initialize_context, intialize_workplane
from ezmesh.geometry.transaction import GeoEntity, GeoTransaction, MeshContext
from ezmesh.geometry.field import ExtrudedBoundaryLayer, TransfiniteCurveField, TransfiniteSurfaceField, TransfiniteVolumeField
from ezmesh.geometry.plot import plot_entities
from ezmesh.geometry.volume import Volume
from ezmesh.mesh import Mesh
from ezmesh.utils.geometry import generate_mesh, commit_transactions
from jupyter_cadquery import show
from cadquery.selectors import InverseSelector

from ezmesh.visualizer import visualize_mesh

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
        self.transactions = []
        self.mesh: Optional[Mesh] = None
        self.ctx = MeshContext()

    def __enter__(self):
        gmsh.initialize()

        self.ctx = initialize_context(self.workplane)
        intialize_workplane(self.workplane, self.ctx)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

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
            tagged_cq_objects += get_cq_objects_as_type(tagged_workspace, type(cq_objects[0]))
        tagged_cq_object_ids = [get_entity_id(tagged_cq_object) for tagged_cq_object in tagged_cq_objects] 

        for cq_object in cq_objects:
            id = get_entity_id(cq_object)
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

    def vals(self) -> Sequence[GeoEntity]:
        return select_entities(self.workplane, self.ctx)

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
            points = select_entities(point_select(self.workplane), self.ctx)
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

    def generate(self, dim: int = 3):
        self.mesh = generate_mesh([*self.vals(), *self.transactions], dim, self.ctx)
        self.reset()
        return self

    def write(self, filename: str, dim: int = 3):
        if self.mesh is None:
            self.generate(dim)
        assert self.mesh is not None
        if filename.endswith(".su2"):
            export_to_su2(self.mesh, filename)
        else:
            gmsh.write(filename)
        return self

    def show(self, type: Literal["fltk", "mesh", "cadquery", "plot"] = "cadquery"):
        if type == "fltk":
            gmsh.fltk.run()
        elif type == "mesh":
            assert self.mesh is not None, "Mesh is not generated yet."
            visualize_mesh(self.mesh)
        elif type == "plot":
            entities = self.vals()
            plot_entities(entities)
        else:
            show(self.workplane)
        return self


    def close(self):
        gmsh.finalize()
