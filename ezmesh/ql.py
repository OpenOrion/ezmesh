import gmsh
import cadquery as cq
from cadquery.cq import CQObject
from typing import Callable, Iterable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
from ezmesh.entity import EntityTypeString
from ezmesh.transaction import TransactionContext
from ezmesh.transactions.algorithm import MeshAlgorithm2DType, SetMeshAlgorithm
from ezmesh.transactions.boundary_layer import UnstructuredBoundaryLayer
from ezmesh.transactions.physical_group import SetPhysicalGroup
from ezmesh.transactions.refinement import Recombine, Refine, SetMeshSize, SetSmoothing
from ezmesh.transactions.transfinite import SetTransfiniteEdge, SetTransfiniteFace, SetTransfiniteSolid, TransfiniteArrangementType, TransfiniteMeshType
from ezmesh.mesh.exporters import export_to_su2
from ezmesh.cq import CQEntityContext, EntityType, Partition, get_selector, import_workplane, partition_workplane, plot_workplane, tag_workplane
from ezmesh.utils.cq import CQUtils
from ezmesh.visualizer import visualize_mesh
from jupyter_cadquery import show

class GeometryQL:
    _workplane: cq.Workplane
    _initial_workplane: cq.Workplane
    def __init__(self) -> None:
        self._initial_workplane = self._workplane = None # type: ignore
        self._ctx = TransactionContext()
        self.is_structured = False
        self.partition_groups: dict[CQObject, list[list[CQObject]]] = {}
    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def end(self, num: Optional[int] = None):
        if num is None:
            self._workplane = self._initial_workplane
        else:
            self._workplane = self._workplane.end(num)
        return self

    def load(self, target: Union[cq.Workplane, str, Iterable[CQObject]], partitions: Optional[Sequence[Partition]] = None):
        assert self._workplane is None, "Workplane is already loaded."

        self._pre_partition_workplane = workplane = import_workplane(target)
        partition_faces = None

        if partitions:
            result = partition_workplane(self._pre_partition_workplane, partitions)
            workplane = result.workplane
            partition_faces = result.faces
            self.partition_groups = result.groups
            

        self._workplane = self._initial_workplane = workplane
        self._entity_ctx = CQEntityContext(self._workplane, partition_faces)
        
        topods = self._workplane.toOCC()
        gmsh.model.occ.importShapesNativePointer(topods._address())
        gmsh.model.occ.synchronize()

        tag_workplane(self._workplane, self._entity_ctx)
        return self    
    
    def solids(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._entity_ctx.cq_registry, selector, indices, is_interior)
        self._workplane = self._workplane.solids(selector, tag)
        return self

    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._entity_ctx.cq_registry, selector, indices, is_interior)
        self._workplane = self._workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._entity_ctx.cq_registry, selector, indices, is_interior)
        self._workplane = self._workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._entity_ctx.cq_registry, selector, indices, is_interior)
        self._workplane = self._workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._entity_ctx.cq_registry, selector, indices, is_interior)
        self._workplane = self._workplane.vertices(selector, tag)
        return self

    def vals(self):
        return self._entity_ctx.select_many(self._workplane)

    def tag(self, names: Union[str, Sequence[str]]):
        if isinstance(names, str):
            self._workplane.tag(names)
        else:
            for i, cq_obj in enumerate(self._workplane.vals()):
                self._workplane.newObject([cq_obj]).tag(names[i])
        return self

    def fromTagged(self, tags: Union[str, Iterable[str]], type: Optional[EntityTypeString] = None, invert: bool = True):        
        if isinstance(tags, str) and type is None:
            self._workplane = self._workplane._getTagged(tags)
        elif type is not None:
            entity_type = EntityType.resolve(type)
            tagged_objs = CQUtils.select_tagged(self._workplane, tags, entity_type)
            workplane_objs = CQUtils.select(self._workplane, entity_type)
            filtered_objs = CQUtils.filter(workplane_objs, tagged_objs, invert)
            self._workplane = self._workplane.newObject(filtered_objs)
        return self

    def addPhysicalGroup(self, names: Union[str, Sequence[str]], tagWorkspace: bool = True):
        for name in (names if isinstance(names, str) else names):
            set_physical_group = SetPhysicalGroup(self.vals(), name)
            self._ctx.add_transaction(set_physical_group)
        if tagWorkspace:
            self.tag(names)
        return self

    def recombine(self, angle: float = 45):
        faces = self._entity_ctx.select_many(self._workplane, EntityType.face)
        recombines = [Recombine(face, angle) for face in faces]
        self._ctx.add_transactions(recombines)
        return self

    def setMeshSize(self, size: Union[float, Callable[[float,float,float], float]]):
        points = self._entity_ctx.select_many(self._workplane, EntityType.vertex)
        set_size = SetMeshSize(points, size)
        self._ctx.add_transaction(set_size)
        return self

    def setMeshAlgorithm(self, type: MeshAlgorithm2DType, per_face: bool = False):
        faces = self._entity_ctx.select_many(self._workplane, EntityType.face)
        set_algorithms = [SetMeshAlgorithm(face, type, per_face) for face in faces]
        self._ctx.add_transactions(set_algorithms)
        return self

    def smooth(self, num_smooths = 1):
        faces = self._entity_ctx.select_many(self._workplane)
        set_smoothings = [SetSmoothing(face, num_smooths) for face in faces]
        self._ctx.add_transactions(set_smoothings)
        return self

    def refine(self, num_refines = 1):
        refine = Refine(num_refines)
        self._ctx.add_transaction(refine)
        return self

    def setTransfiniteEdge(self, num_node: Union[Sequence[int], int], mesh_type: Union[TransfiniteMeshType, Sequence[TransfiniteMeshType]] = "Progression", coef: Union[float, Sequence[float]] = 1.0):
        edge_batch = self._entity_ctx.select_batch(self._workplane, EntityType.face, EntityType.edge)
        for edges in edge_batch:
            set_transfinite_edges = [SetTransfiniteEdge(
                edge, 
                num_node if isinstance(num_node, int) else num_node[i], 
                mesh_type if isinstance(mesh_type, str) else mesh_type[i], 
                coef if isinstance(coef, float) else coef[i]
            ) for i,edge in enumerate(edges)]
            self._ctx.add_transactions(set_transfinite_edges)

        return self

    def setTransfiniteFace(self, arrangement: TransfiniteArrangementType = "Left", corner_indexes: Sequence[int] = []):
        cq_face_batch = CQUtils.select_batch(self._workplane, EntityType.solid, EntityType.face)
        for i, cq_faces in enumerate(cq_face_batch):
            faces = self._entity_ctx.select_many(cq_faces)
            set_transfinite_faces = [SetTransfiniteFace(face, arrangement) for face in faces]
            self._ctx.add_transactions(set_transfinite_faces)

        return self

    def setTransfiniteSolid(self):
        self.is_structured = True    
        solids = self._entity_ctx.select_many(self._workplane, EntityType.solid)
        set_transfinite_solids = [SetTransfiniteSolid(solid) for solid in solids]
        self._ctx.add_transactions(set_transfinite_solids)
        return self

    def setTransfiniteAuto(self):
        self.setTransfiniteSolid()
        cq_face_batch =  CQUtils.select_batch(self._workplane, EntityType.solid, EntityType.face)
        for cq_faces in cq_face_batch:
            for cq_face in cq_faces:
                # sort vertices
                face = self._entity_ctx.select(cq_face)


                set_transfinite_face = SetTransfiniteFace(face)
                self._ctx.add_transaction(set_transfinite_face)

                for sorted_path in self.partition_groups[cq_face]:
                    edge = self._entity_ctx.select(sorted_path[0])
                    set_transfinite_edge = SetTransfiniteEdge(edge, 50, "Progression", 1.0)
                    self._ctx.add_transaction(set_transfinite_edge)
                    
        return self

    def addBoundaryLayer(self, ratio: float = 1, hwall_n: Optional[float] = None, num_layers: Optional[int] = None):
        if self.is_structured:
            boundary_vertices = self._entity_ctx.select_many(self._workplane, EntityType.vertex)
            try:
                for (cq_edge, edge) in self._entity_ctx.entity_registries[EntityType.edge].items():
                    transaction = cast(SetTransfiniteEdge, self._ctx.get_transaction(SetTransfiniteEdge, edge))
                    curr_vertices =  self._entity_ctx.select_many(cq_edge.Vertices()) # type: ignore
                    transaction.update_from_boundary_layer(boundary_vertices, curr_vertices, cq_edge.Length(), ratio, hwall_n, num_layers) # type: ignore
            except KeyError:
                raise Exception("Structured boundary layer can only be applied after setTransfiniteEdge")
        else:
            assert num_layers is not None and hwall_n is not None and ratio is not None, "num_layers, hwall_n and ratio must be specified for unstructured boundary layer"
            boundary_layer = UnstructuredBoundaryLayer(self.vals(), ratio, hwall_n, num_layers)
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

    def show(self, type: Literal["fltk", "mesh", "cq", "plot"] = "cq"):
        if type == "fltk":
            gmsh.fltk.run()
        elif type == "mesh":
            assert self._ctx.mesh is not None, "Mesh is not generated yet."
            visualize_mesh(self._ctx.mesh)
        elif type == "plot":
            plot_workplane(self._workplane, self._entity_ctx)
        else:
            show(self._workplane, theme="dark")
        return self


    def close(self):
        gmsh.finalize()
