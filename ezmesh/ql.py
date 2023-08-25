import gmsh
import cadquery as cq
from cadquery.cq import CQObject
from typing import Callable, Iterable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
import numpy as np
from ezmesh.entity import Entity, EntityTypeString
from ezmesh.transaction import TransactionContext
from ezmesh.transactions.algorithm import MeshAlgorithm2DType, SetMeshAlgorithm
from ezmesh.transactions.boundary_layer import UnstructuredBoundaryLayer
from ezmesh.transactions.physical_group import SetPhysicalGroup
from ezmesh.transactions.refinement import Recombine, Refine, SetMeshSize, SetSmoothing
from ezmesh.transactions.transfinite import SetTransfiniteEdge, SetTransfiniteFace, SetTransfiniteSolid, TransfiniteArrangementType, TransfiniteMeshType, get_num_nodes_for_ratios
from ezmesh.mesh.exporters import export_to_su2
from ezmesh.cq import CQEntityContext, EntityType, get_edge_angle, get_plane, get_selector, import_workplane, split_workplane, plot_workplane, tag_workplane
from ezmesh.utils.cq import CQExtensions, CQGroupTypeString, CQLinq
from ezmesh.utils.types import OrderedSet
from ezmesh.visualizer import visualize_mesh
from jupyter_cadquery import show

class GeometryQL:
    _workplane: cq.Workplane
    _initial_workplane: cq.Workplane
    def __init__(self) -> None:
        self._initial_workplane = self._workplane = None # type: ignore
        self._ctx = TransactionContext()
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

    def load(self, target: Union[cq.Workplane, str, Iterable[CQObject]], splits: Optional[Callable[[cq.Workplane], Sequence[cq.Face]]] = None):
        assert self._workplane is None, "Workplane is already loaded."

        self._pre_split_workplane = workplane = import_workplane(target)

        if splits:
            result = split_workplane(self._pre_split_workplane, splits(self._pre_split_workplane))
            workplane = result.workplane
            self._split_faces = result.faces
            
        self._workplane = self._initial_workplane = workplane
        self._entity_ctx = CQEntityContext(self._workplane)
        self._groups = CQLinq.group(self._workplane)

        topods = self._workplane.toOCC()
        gmsh.model.occ.importShapesNativePointer(topods._address())
        gmsh.model.occ.synchronize()

        tag_workplane(self._workplane, self._entity_ctx)
        return self    
    
    def solids(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, groupType: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        group = groupType and self._groups[groupType]
        selector = get_selector(selector, group, indices)
        self._workplane = self._workplane.solids(selector, tag)
        return self

    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, type: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        group = type and self._groups[type]
        selector = get_selector(selector, group, indices)
        self._workplane = self._workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, groupType: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        group = groupType and self._groups[groupType]
        selector = get_selector(selector, group, indices)
        self._workplane = self._workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, groupType: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        group = groupType and self._groups[groupType]
        selector = get_selector(selector, group, indices)
        self._workplane = self._workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None, groupType: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        group = groupType and self._groups[groupType]
        selector = get_selector(selector, group, indices)
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
            tagged_objs = CQLinq.select_tagged(self._workplane, tags, entity_type)
            workplane_objs = CQLinq.select(self._workplane, entity_type)
            filtered_objs = CQLinq.filter(workplane_objs, tagged_objs, invert)
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
        cq_face_batch = CQLinq.select_batch(self._workplane, EntityType.solid, EntityType.face)
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

    def setTransfiniteAuto(self, num_nodes: int = 50, group_angle = 45):
        # transfinite_auto = SetTransfiniteAuto()
        # self._ctx.add_transaction(transfinite_auto)
        self.setTransfiniteSolid()
        cq_face_batch =  CQLinq.select_batch(self._workplane, EntityType.solid, EntityType.face)
        
        edge_transactions = []
        for cq_faces in [*list(cq_face_batch)]:
            for cq_face in [*list(cq_faces)]:
                sorted_paths = CQLinq.sort(cq_face.Edges())
                assert sorted_paths[-1].end == sorted_paths[0].start, "Edges do not form a closed loop"
                prev_path = sorted_paths[-1]
                angles = []
                for path in sorted_paths: # type: ignore
                    angle = get_edge_angle(prev_path.edge, path.edge)
                    angles.append(angle)
                    prev_path = path

                
                shuffle_num = 0
                for angle in angles:
                    if angle > np.radians(group_angle):
                        break
                    shuffle_num += 1

                cq_corners = []
                edges_groups: list[list[cq.Edge]] = []
                for i, angle in enumerate(angles[shuffle_num:] + angles[:shuffle_num]):
                    path = sorted_paths[i+shuffle_num]
                    if angle > np.radians(group_angle):
                        edges_groups.append([])
                        cq_corners.append(path.start)
                    edges_groups[-1].append(path.edge)

                if len(edges_groups) != 4:
                    plot_workplane(cq_face)
                assert len(edges_groups) == 4, "Face must have 4 corners"

                face = self._entity_ctx.select(cq_face)
                corners = self._entity_ctx.select_many(cq_corners)
                set_transfinite_face = SetTransfiniteFace(face, corners=corners)
                self._ctx.add_transaction(set_transfinite_face)
                # CQExtensions.plot_groups(edges_groups)
                for i, cq_edges in enumerate(edges_groups):
                    group_length = np.sum([cq_edge.Length() for cq_edge in cq_edges])
                    ratios = [cq_edge.Length()/group_length for cq_edge in cq_edges]
                    edge_num_nodes = get_num_nodes_for_ratios(num_nodes, ratios)
                    # print(edge_num_nodes)
                    for j, cq_edge in enumerate(cq_edges):
                        assert edge_num_nodes[j] != 0, "edge nodes of 0 detected, raise the num_nodes"
                        edge = self._entity_ctx.select(cq_edge)
                        # print(edge.tag, edge_num_nodes[j])
                        set_transfinite_edge = SetTransfiniteEdge(edge, edge_num_nodes[j], "Progression", 1.0)
                        edge_transactions.append(set_transfinite_edge)
                        # self._ctx.add_transaction(set_transfinite_edge)

        self._ctx.add_transactions(edge_transactions, ignore_duplicates=True)


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
