import gmsh
import cadquery as cq
from cadquery.cq import CQObject
from typing import Callable, Iterable, Literal, Optional, Sequence, Union
from cadquery.selectors import Selector
from ezmesh.context import Context
from ezmesh.entity import EntityTypeString
from ezmesh.transactions.algorithm import MeshAlgorithm2DType, SetMeshAlgorithm
from ezmesh.transactions.boundary_layer import BoundaryLayer
from ezmesh.transactions.physical_group import SetPhysicalGroup
from ezmesh.transactions.refinement import Recombine, Refine, SetMeshSize, SetSmoothing
from ezmesh.transactions.transfinite import SetTransfiniteEdge, SetTransfiniteFace, SetTransfiniteSolid, TransfiniteArrangementType, TransfiniteMeshType
from ezmesh.mesh.exporters import export_to_su2
from ezmesh.occ import EntityType, OCCMap, filter_occ_objs, select_occ_objs, select_tagged_occ_objs
from ezmesh.cq import Parition, get_selector, import_workplane, plot_workplane, tag_workplane_entities
from ezmesh.visualizer import visualize_mesh
from jupyter_cadquery import show

class GeometryQL:
    _workplane: cq.Workplane
    _initial_workplane: cq.Workplane
    def __init__(self) -> None:
        self._initial_workplane = self._workplane = None # type: ignore
        self._ctx = Context()

    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def end(self):
        self._workplane = self._initial_workplane
        return self

    def load(self, target: Union[cq.Workplane, str, Iterable[CQObject]], partitions: Optional[Sequence[Parition]] = None):
        assert self._workplane is None, "Workplane is already loaded."

        self._initial_workplane = self._workplane = import_workplane(target, partitions)

        topods = self._workplane.toOCC()
        gmsh.model.occ.importShapesNativePointer(topods._address())
        gmsh.model.occ.synchronize()
        self._occ_map = OCCMap(self._workplane)

        tag_workplane_entities(self._workplane, self._occ_map)
        return self    
    
    def solids(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None):
        selector = get_selector(self._workplane, selector, is_interior)
        self._workplane = self._workplane.solids(selector, tag)
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
        selector = get_selector(self._workplane, selector)
        self._workplane = self._workplane.vertices(selector, tag)
        return self

    def vals(self):
        return self._occ_map.select_entities(self._workplane)

    def tag(self, names: Union[str, Sequence[str]]):
        if isinstance(names, str):
            self._workplane.tag(names)
        else:
            for i, occ_obj in enumerate(self._workplane.vals()):
                self._workplane.newObject([occ_obj]).tag(names[i])
        return self

    def fromTagged(self, tags: Union[str, Iterable[str]], type: Optional[EntityTypeString] = None, is_included: bool = True):        
        if isinstance(tags, str) and type is None:
            self._workplane = self._workplane._getTagged(tags)
        elif type is not None:
            entity_type = EntityType.resolve(type)
            occ_tagged_objs = select_tagged_occ_objs(self._workplane, tags, entity_type)
            occ_occ_objs = select_occ_objs(self._workplane, entity_type)
            occ_filtered_objs = filter_occ_objs(occ_occ_objs, occ_tagged_objs, is_included)
            self._workplane = self._workplane.newObject(occ_filtered_objs)
        return self

    def addPhysicalGroup(self, names: Union[str, Sequence[str]], tagWorkspace: bool = True):
        for name in (names if isinstance(names, str) else names):
            set_physical_group = SetPhysicalGroup(self.vals(), name)
            self._ctx.add_transaction(set_physical_group)
        if tagWorkspace:
            self.tag(names)
        return self

    def recombine(self, angle: float = 45):
        faces = self._occ_map.select_entities(self._workplane, EntityType.face)
        recombine = Recombine(faces, angle)
        self._ctx.add_transaction(recombine)
        return self

    def setMeshSize(self, size: Union[float, Callable[[float,float,float], float]]):
        points = self._occ_map.select_entities(self._workplane, EntityType.vertex)
        set_size = SetMeshSize(points, size)
        self._ctx.add_transaction(set_size)
        return self

    def setMeshAlgorithm(self, type: MeshAlgorithm2DType, per_face: bool = False):
        faces = self._occ_map.select_entities(self._workplane, EntityType.face)
        set_algorithm = SetMeshAlgorithm(faces, type, per_face)
        self._ctx.add_transaction(set_algorithm)
        return self

    def smooth(self, num_smooths = 1):
        faces = self._occ_map.select_entities(self._workplane)
        set_smoothing = SetSmoothing(faces, num_smooths)
        self._ctx.add_transaction(set_smoothing)
        return self

    def refine(self, num_refines = 1):
        refine = Refine(num_refines)
        self._ctx.add_transaction(refine)
        return self

    def setTransfiniteEdge(self, num_nodes: Sequence[int], mesh_type: Union[TransfiniteMeshType, Sequence[TransfiniteMeshType]] = "Progression", coef: Union[float, Sequence[float]] = 1.0):
        edge_batch = self._occ_map.select_batch_entities(self._workplane, EntityType.face, EntityType.edge)
        for edges in edge_batch:
            set_transfinite_edge = SetTransfiniteEdge(edges, num_nodes, mesh_type, coef)
            self._ctx.add_transaction(set_transfinite_edge)

        return self

    def setTransfiniteFace(self, arrangement: TransfiniteArrangementType = "Left"):
        face_batch = self._occ_map.select_batch_entities(self._workplane, EntityType.solid, EntityType.face)
        for faces in face_batch:
            set_transfinite_face = SetTransfiniteFace(faces, arrangement)
            self._ctx.add_transaction(set_transfinite_face)

        return self

    def setTransfiniteSolid(
        self, 
        num_nodes: Optional[Sequence[int]] = None, 
        mesh_type: Union[TransfiniteMeshType, Sequence[TransfiniteMeshType]] = "Progression", 
        coef: Union[float, Sequence[float]] = 1.0, 
        arrangement: TransfiniteArrangementType = "Left"
    ):            
        solids = self._occ_map.select_entities(self._workplane, EntityType.solid)
        set_transfinite_solid = SetTransfiniteSolid(solids)
        self._ctx.add_transaction(set_transfinite_solid)
        if num_nodes is not None:
            self.setTransfiniteFace(arrangement)
            self.setTransfiniteEdge(num_nodes, mesh_type, coef)
        return self

    def addBoundaryLayer(self, num_layers: int, hwall_n: float, ratio: float):
        boundary_layer = BoundaryLayer(self.vals(), num_layers, hwall_n, ratio)
        self._ctx.add_transaction(boundary_layer)
        return self

    def generate(self, dim: int = 3):
        self._ctx.commit(dim)
        return self

    def write(self, filename: str, dim: int = 3):
        if self._ctx.mesh is None:
            self.generate(dim)
        assert self._ctx.mesh is not None
        if filename.endswith(".su2"):
            export_to_su2(self._ctx.mesh, filename)
        else:
            gmsh.write(filename)
        return self

    def show(self, type: Literal["fltk", "mesh", "cadquery", "plot"] = "cadquery"):
        if type == "fltk":
            gmsh.fltk.run()
        elif type == "mesh":
            assert self._ctx.mesh is not None, "Mesh is not generated yet."
            visualize_mesh(self._ctx.mesh)
        elif type == "plot":
            plot_workplane(self._workplane, self._occ_map)
        else:
            show(self._workplane, theme="dark")
        return self


    def close(self):
        gmsh.finalize()
