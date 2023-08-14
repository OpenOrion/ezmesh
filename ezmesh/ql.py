import gmsh
import cadquery as cq
from typing import Callable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
from ezmesh import export_to_su2
from ezmesh.geometry.transactions import Point
from ezmesh.geometry.transactions.curve import Curve
from ezmesh.geometry.transactions.plane_surface import PlaneSurface
from ezmesh.geometry.transactions.volume import Volume
from ezmesh.mesh import Mesh
from ezmesh.mesh.transactions.boundary_layer import BoundaryLayer
from ezmesh.mesh.transactions.refinement import Recombine
from ezmesh.utils.cadquery import OCPContext, initialize_context, initialize_gmsh_from_cq, intialize_workplane, get_selector, select_ocp_type
from ezmesh.geometry.transaction import GeoEntity, GeoTransaction, GeoContext
from ezmesh.mesh.transaction import MeshTransaction, generate_mesh
from jupyter_cadquery import show
from ezmesh.mesh.visualizer import visualize_mesh
from ezmesh.geometry.plot import plot_entities

class Geometry:

    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def generate(self, transactions: Union[GeoTransaction, Sequence[GeoTransaction]], mesh_transactions: Sequence[MeshTransaction] = []):
        transactions = transactions if isinstance(transactions, Sequence) else [transactions]
        dim = 3 if isinstance(transactions[0], Volume) else 2
        ctx = GeoContext(dim)
        self.mesh = generate_mesh(transactions, mesh_transactions, ctx, dim)
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
        if isinstance(self._workplane.vals()[0], cq.Wire):
            self._workplane = self._workplane.extrude(-0.001).faces(">Z")
        self._initial_workplane = self._workplane

        dim = 2 if isinstance(self._workplane.vals()[0], cq.Face) else 3
        self._geo_ctx = GeoContext(dim)
        self._ocp_ctx = OCPContext(dim)

        initialize_gmsh_from_cq(self._workplane)
        initialize_context(self._workplane, self._ocp_ctx)
        intialize_workplane(self._workplane, self._ocp_ctx)

        return self

    # def select(self, tags:Union[Sequence[str], str, None], inverse=False):
    #     tags = [tags ]if isinstance(tags, str) else tags or []
    #     cq_objects = self._workplane.vals()
    #     filtered_cq_objects = []

    #     tagged_cq_objects = []
    #     for tag in tags:
    #         tagged_workspace = self._workplane._getTagged(tag)
    #         tagged_cq_objects += select_ocp_type(tagged_workspace, type(cq_objects[0]))
    #     tagged_cq_object_ids = [get_entity_id(tagged_cq_object) for tagged_cq_object in tagged_cq_objects] 

    #     for cq_object in cq_objects:
    #         id = get_entity_id(cq_object)
    #         if (not inverse and id in tagged_cq_object_ids) or (inverse and id not in tagged_cq_object_ids):
    #             filtered_cq_objects.append(cq_object)

    #     self._workplane = self._workplane.newObject(filtered_cq_objects)
    #     return self


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

    def vals(self):
        return list(self._ocp_ctx.select_many(self._workplane.vals()))

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
        return self


    def recombine(self, angle: float):
        faces = cast(Sequence[cq.Face], select_ocp_type(self._workplane, cq.Face))
        surfaces = self._ocp_ctx.select_many(faces)
        self._mesh_transactions += [Recombine(surface, angle) for surface in surfaces]
        return self

    def setMeshSize(self, mesh_size: Union[float, Callable[[Point], float]]):
        vertices = cast(Sequence[cq.Vertex],select_ocp_type(self._workplane, cq.Vertex))
        points = self._ocp_ctx.select_many(vertices)
        for point in cast(Sequence[Point], points):
            if isinstance(mesh_size, Callable):
                mesh_size = mesh_size(point)
            point.set_mesh_size(mesh_size)
        return self

    def addBoundaryLayer(self, num_layers: int, hwall_n: float, ratio: float):
        target = cast(Sequence[Union[PlaneSurface, Curve]], self.vals())
        ext_bnd_layer = BoundaryLayer(target, num_layers, hwall_n, ratio)
        self._mesh_transactions.append(ext_bnd_layer)
        return self

    def generate(self, dim: int = 3):
        self._mesh = generate_mesh(self.vals(), self._mesh_transactions, self._geo_ctx, dim)
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
            plot_entities(self.vals())
        else:
            show(self._workplane)
        return self


    def close(self):
        gmsh.finalize()
