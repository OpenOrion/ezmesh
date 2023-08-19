import gmsh
import cadquery as cq
from cadquery.cq import CQObject
from typing import Callable, Iterable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
from ezmesh.context import Context
from ezmesh.entity import EntityTypeString
from ezmesh.transactions.algorithm import MeshAlgorithm2DType, SetMeshAlgorithm
from ezmesh.transactions.boundary_layer import BoundaryLayer
from ezmesh.transactions.physical_group import SetPhysicalGroup
from ezmesh.transactions.refinement import Recombine, Refine, SetMeshSize, SetSmoothing
from ezmesh.transactions.transfinite import SetTransfiniteEdge, SetTransfiniteFace, SetTransfiniteSolid, TransfiniteArrangementType, TransfiniteMeshType
from ezmesh.mesh.exporters import export_to_su2
from ezmesh.occ import EntityType, OCCMap, filter_occ_objs, select_batch_occ_objs, select_occ_objs, select_tagged_occ_objs
from ezmesh.cq import Parition, get_partitioned_workplane, get_selector, import_workplane, plot_workplane, tag_workplane_entities
from ezmesh.utils.types import OrderedSet
from ezmesh.visualizer import visualize_mesh
from jupyter_cadquery import show

class GeometryQL:
    _workplane: cq.Workplane
    _initial_workplane: cq.Workplane
    def __init__(self) -> None:
        self._initial_workplane = self._workplane = None # type: ignore
        self._ctx = Context()
        self.is_structured = False
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

    def load(self, target: Union[cq.Workplane, str, Iterable[CQObject]], partitions: Optional[Sequence[Parition]] = None):
        assert self._workplane is None, "Workplane is already loaded."

        self._pre_partition_workplane = workplane = import_workplane(target)

        if partitions:
            workplane = get_partitioned_workplane(self._pre_partition_workplane, partitions)

        self._workplane = self._initial_workplane = workplane
        self._occ_map = OCCMap(self._workplane)
        self._occ_map.init_interior(self._pre_partition_workplane)
        
        topods = self._workplane.toOCC()
        gmsh.model.occ.importShapesNativePointer(topods._address())
        gmsh.model.occ.synchronize()

        tag_workplane_entities(self._workplane, self._occ_map)
        return self    
    
    def solids(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._occ_map, selector, indices, is_interior)
        self._workplane = self._workplane.solids(selector, tag)
        return self

    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._occ_map, selector, indices, is_interior)
        self._workplane = self._workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._occ_map, selector, indices, is_interior)
        self._workplane = self._workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, is_interior: Optional[bool] = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._occ_map, selector, indices, is_interior)
        self._workplane = self._workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None, indices: Optional[Sequence[int]] = None):
        selector = get_selector(self._occ_map, selector, indices)
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

    def fromTagged(self, tags: Union[str, Iterable[str]], type: Optional[EntityTypeString] = None, invert: bool = True):        
        if isinstance(tags, str) and type is None:
            self._workplane = self._workplane._getTagged(tags)
        elif type is not None:
            entity_type = EntityType.resolve(type)
            occ_tagged_objs = select_tagged_occ_objs(self._workplane, tags, entity_type)
            occ_occ_objs = select_occ_objs(self._workplane, entity_type)
            occ_filtered_objs = filter_occ_objs(occ_occ_objs, occ_tagged_objs, invert)
            self._workplane = self._workplane.newObject(occ_filtered_objs)
        return self

    def addPhysicalGroup(self, names: Union[str, Sequence[str]], tagWorkspace: bool = True):
        for name in (names if isinstance(names, str) else names):
            set_physical_group = SetPhysicalGroup(self.vals(), name)
            self._ctx.add_transaction(set_physical_group)
        if tagWorkspace:
            self.tag(names)
        return self

    # def ignore(self):
    #     self._ctx.ignore(self.vals())
    #     return self

    def recombine(self, angle: float = 45):
        faces = self._occ_map.select_entities(self._workplane, EntityType.face)
        recombines = [Recombine(face, angle) for face in faces]
        self._ctx.add_transactions(recombines)
        return self

    def setMeshSize(self, size: Union[float, Callable[[float,float,float], float]]):
        points = self._occ_map.select_entities(self._workplane, EntityType.vertex)
        set_size = SetMeshSize(points, size)
        self._ctx.add_transaction(set_size)
        return self

    def setMeshAlgorithm(self, type: MeshAlgorithm2DType, per_face: bool = False):
        faces = self._occ_map.select_entities(self._workplane, EntityType.face)
        set_algorithms = [SetMeshAlgorithm(face, type, per_face) for face in faces]
        self._ctx.add_transactions(set_algorithms)
        return self

    def smooth(self, num_smooths = 1):
        faces = self._occ_map.select_entities(self._workplane)
        set_smoothings = [SetSmoothing(face, num_smooths) for face in faces]
        self._ctx.add_transactions(set_smoothings)
        return self

    def refine(self, num_refines = 1):
        refine = Refine(num_refines)
        self._ctx.add_transaction(refine)
        return self

    def setTransfiniteEdge(self, num_node: Union[Sequence[int], int], mesh_type: Union[TransfiniteMeshType, Sequence[TransfiniteMeshType]] = "Progression", coef: Union[float, Sequence[float]] = 1.0):
        edge_batch = self._occ_map.select_batch_entities(self._workplane, EntityType.face, EntityType.edge)
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
        occ_face_batch = select_batch_occ_objs(self._workplane, EntityType.solid, EntityType.face)
        for i, occ_faces in enumerate(occ_face_batch):
            faces = self._occ_map.select_entities(occ_faces)
            set_transfinite_faces = [SetTransfiniteFace(face, arrangement) for face in faces]
            self._ctx.add_transactions(set_transfinite_faces)

        return self

    def setTransfiniteSolid(self):
        self.is_structured = True    
        solids = self._occ_map.select_entities(self._workplane, EntityType.solid)
        set_transfinite_solids = [SetTransfiniteSolid(solid) for solid in solids]
        self._ctx.add_transactions(set_transfinite_solids)
        return self

    def setTransfiniteAuto(self):
        self.setTransfiniteSolid()
        occ_face_batch =  select_batch_occ_objs(self._workplane, EntityType.solid, EntityType.face)
        for occ_faces in occ_face_batch:
            for occ_face in occ_faces:
                vertices = self._occ_map.select_entities([occ_face], EntityType.vertex)
                face = self._occ_map.select_entity(occ_face)
                set_transfinite_face = SetTransfiniteFace(face, corners=vertices)
                self._ctx.add_transaction(set_transfinite_face)
                edges = self._occ_map.select_entities([occ_face], EntityType.edge)
                for edge in edges:
                    set_transfinite_edge = SetTransfiniteEdge(edge, 50, "Progression", 1.0)
                    self._ctx.add_transaction(set_transfinite_edge)
                    
        return self

    def addBoundaryLayer(self, num_layers: int, wall_height: float, ratio: float):
        if self.is_structured:
            all_occ_edges = select_occ_objs(self._initial_workplane, EntityType.edge)
            boundary_occ_vertices = OrderedSet(select_occ_objs(self._workplane, EntityType.vertex))
            for occ_edge in all_occ_edges:
                edge = self._occ_map.select_entity(occ_edge)
                transaction = self._ctx.get_transaction(SetTransfiniteEdge, edge)
                assert isinstance(transaction, SetTransfiniteEdge), "setTransfiniteAuto must be invoked before addBoundaryLayer."
                occ_vertices = occ_edge.Vertices()
                if occ_vertices[0] in boundary_occ_vertices or occ_vertices[-1] in boundary_occ_vertices:
                    if occ_vertices[0] in boundary_occ_vertices:
                        transaction.coef = -0.85
                    elif occ_vertices[-1] in boundary_occ_vertices:
                        transaction.coef = 0.85
                    else:
                        raise Exception("This should not happen.")
        else:
            boundary_layer = BoundaryLayer(self.vals(), num_layers, wall_height, ratio)
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
