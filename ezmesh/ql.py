import gmsh
import cadquery as cq
from typing import Callable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
from ezmesh import export_to_su2
from ezmesh.geometry.transactions import Point, PlaneSurface
from ezmesh.mesh import Mesh
from ezmesh.mesh.transactions.refinement import Recombine
from ezmesh.utils.cadquery import CQObject3D, get_entity_id, get_cq_objects_as_type, select_entities, get_selector, initialize_context, intialize_workplane
from ezmesh.geometry.transaction import GeoEntity, GeoTransaction, Context
# from ezmesh.mesh.transactions.transfinite import ExtrudedBoundaryLayer
from ezmesh.mesh.transaction import MeshTransaction, generate_mesh
from jupyter_cadquery import show
from ezmesh.mesh.visualizer import visualize_mesh
from ezmesh.geometry.plot import plot_entities

class Geometry:
    def __init__(self) -> None:
        self.ctx = Context()

    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def generate(self, transactions: Union[GeoTransaction, Sequence[GeoTransaction]], mesh_transactions: Sequence[MeshTransaction] = []):
        transactions = transactions if isinstance(transactions, Sequence) else [transactions]
        self.ctx.dimension = 2 if isinstance(transactions[0], PlaneSurface) else 3
        self.mesh = generate_mesh(transactions, mesh_transactions, self.ctx, self.ctx.dimension)
        return self.mesh

    def write(self, filename: str):
        if filename.endswith(".su2"):
            export_to_su2(self.mesh, filename)
        else:
            gmsh.write(filename)


class GeometryQL:
    _workplane: cq.Workplane
    _initial_workplane: cq.Workplane
    def __init__(self) -> None:
        self._geo_transactions: list[GeoTransaction] = []
        self._mesh_transactions: list[MeshTransaction] = []

        self._mesh: Optional[Mesh] = None
        self._initial_workplane = self._workplane = None # type: ignore
    
    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def end(self):
        self._workplane = self._initial_workplane
        return self
    
    def load(self, target: Union[cq.Workplane, str]):
        assert self._workplane is None, "Workplane is already loaded."
        if isinstance(target, str):
            self._workplane = cq.importers.importStep(target)
        else:
            self._workplane = target
        dim = 3 if isinstance(self._workplane.vals()[0], CQObject3D) else 2

        if isinstance(self._workplane.vals()[0], cq.occ_impl.shapes.Wire):
            self._workplane = self._workplane.extrude(0.001).faces(">Z")
        self._initial_workplane = self._workplane

        self._ctx = Context(dim)

        initialize_context(self._workplane, self._ctx)
        intialize_workplane(self._workplane, self._ctx)
        return self

    def select(self, tags:Union[Sequence[str], str, None], inverse=False):
        tags = [tags ]if isinstance(tags, str) else tags or []
        cq_objects = self._workplane.vals()
        filtered_cq_objects = []

        tagged_cq_objects = []
        for tag in tags:
            tagged_workspace = self._workplane._getTagged(tag)
            tagged_cq_objects += get_cq_objects_as_type(tagged_workspace, type(cq_objects[0]))
        tagged_cq_object_ids = [get_entity_id(tagged_cq_object) for tagged_cq_object in tagged_cq_objects] 

        for cq_object in cq_objects:
            id = get_entity_id(cq_object)
            if (not inverse and id in tagged_cq_object_ids) or (inverse and id not in tagged_cq_object_ids):
                filtered_cq_objects.append(cq_object)

        self._workplane = self._workplane.newObject(filtered_cq_objects)
        return self


    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None):
        selector = get_selector(self._workplane, selector, is_interior)
        self._workplane = self._workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None):
        selector = get_selector(self._workplane, selector, is_interior)
        self._workplane = self._workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None):
        selector = get_selector(self._workplane, selector, is_interior)
        self._workplane = self._workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None):
        self._workplane = self._workplane.vertices(selector, tag)
        return self

    def vals(self) -> Sequence[GeoEntity]:
        return select_entities(self._workplane.vals(), self._ctx)

    def tag(self, name: str):
        self._workplane = self._workplane.tag(name)
        return self

    def fromTagged(self, name: str):
        self._workplane = self._workplane._getTagged(name)
        self.level = 0
        return self

    def addPhysicalGroup(self, name: str, tagWorkspace: bool = True):
        for entity in self.vals():
            entity.set_label(name)
        if tagWorkspace:
            self.tag(name)
        # self.reset()
        return self


    def recombine(self, angle: float):
        faces = get_cq_objects_as_type(self._workplane, cq.occ_impl.shapes.Face)
        surfaces = select_entities(faces, self._ctx)
        self._mesh_transactions += [Recombine(surface, angle) for surface in surfaces]
        # self.reset()
        return self

    def setMeshSize(self, mesh_size: Union[float, Callable[[Point], float]]):
        vertices = get_cq_objects_as_type(self._workplane, cq.occ_impl.shapes.Vertex)
        points = select_entities(vertices, self._ctx)
        for point in cast(Sequence[Point], points):
            if isinstance(mesh_size, Callable):
                mesh_size = mesh_size(point)
            point.set_mesh_size(mesh_size)
        # self.reset()
        return self

    # def addBoundaryLayer(self, num_layers: int, hwall_n: float, ratio: float):
    #     target = cast(Sequence[Union[PlaneSurface, Edge]], self.vals())
    #     ext_bnd_layer = ExtrudedBoundaryLayer(target, num_layers, hwall_n, ratio)
    #     self._transactions.append(ext_bnd_layer)
    #     # self.reset()
    #     return self

    def generate(self, dim: int = 3):
        self._mesh = generate_mesh(self.vals(), self._mesh_transactions, self._ctx, dim)
        self.end()
        return self

    def write(self, filename: str, dim: int = 3):
        if self._mesh is None:
            self.generate(dim)
        assert self._mesh is not None
        if filename.endswith(".su2"):
            export_to_su2(self._mesh, filename)
        else:
            gmsh.write(filename)
        return self

    def show(self, type: Literal["fltk", "mesh", "cadquery", "plot"] = "cadquery"):
        if type == "fltk":
            gmsh.fltk.run()
        elif type == "mesh":
            assert self._mesh is not None, "Mesh is not generated yet."
            visualize_mesh(self._mesh)
        elif type == "plot":
            entities = self.vals()
            plot_entities(entities)
        else:
            show(self._workplane)
        return self


    def close(self):
        gmsh.finalize()