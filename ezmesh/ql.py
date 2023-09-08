import gmsh
import cadquery as cq
from cadquery.cq import CQObject
from typing import Callable, Iterable, Literal, Optional, Sequence, Union, cast
from cadquery.selectors import Selector
import numpy as np
from ezmesh.entity import CQEntityContext, Entity
from ezmesh.preprocessing.split import split_workplane
from ezmesh.transaction import TransactionContext
from ezmesh.transactions.algorithm import MeshAlgorithm2DType, SetMeshAlgorithm2D
from ezmesh.transactions.boundary_layer import UnstructuredBoundaryLayer, UnstructuredBoundaryLayer2D, get_boundary_num_layers
from ezmesh.transactions.physical_group import SetPhysicalGroup
from ezmesh.transactions.refinement import Recombine, Refine, SetMeshSize, SetSmoothing
from ezmesh.transactions.transfinite import SetTransfiniteEdge, SetTransfiniteFace, SetTransfiniteSolid, TransfiniteArrangementType, TransfiniteMeshType
from ezmesh.mesh.exporters import export_to_su2
from ezmesh.utils.cq import CQ_TYPE_RANKING, CQ_TYPE_STR_MAPPING, CQExtensions, CQGroupTypeString, CQLinq, CQType
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

    def load(self, target: Union[cq.Workplane, str, Iterable[CQObject]], splits: Optional[Callable[[cq.Workplane], Sequence[cq.Face]]] = None, use_cache: bool = True):
        assert self._workplane is None, "Workplane is already loaded."

        split_preprocessing = (lambda workplane: split_workplane(workplane, splits(workplane), use_cache)) if splits else None        
        self._workplane = self._initial_workplane = CQExtensions.import_workplane(target, split_preprocessing)

        topods = self._workplane.toOCC()
        gmsh.model.occ.importShapesNativePointer(topods._address())
        gmsh.model.occ.synchronize()

        self._entity_ctx = CQEntityContext(self._workplane)
        self._type_groups = CQLinq.groupByTypes(self._workplane)

        self._tag_workplane()

        return self    
    

    def _tag_workplane(self):
        "Tag all gmsh entity tags to workplane"
        for cq_type, registry in self._entity_ctx.entity_registries.items():
            for occ_obj in registry.keys():
                tag = f"{cq_type}/{registry[occ_obj].tag}"
                self._workplane.newObject([occ_obj]).tag(tag)

    def solids(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, type: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        obj_type = type and self._type_groups[type]
        selector = CQExtensions.get_selector(selector, obj_type, indices)
        self._workplane = self._workplane.solids(selector, tag)
        return self

    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, type: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        obj_type = type and self._type_groups[type]
        selector = CQExtensions.get_selector(selector, obj_type, indices)
        self._workplane = self._workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, type: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        obj_type = type and self._type_groups[type]
        selector = CQExtensions.get_selector(selector, obj_type, indices)
        self._workplane = self._workplane.edges(selector, tag)
        return self

    def wires(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None, type: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        obj_type = type and self._type_groups[type]
        selector = CQExtensions.get_selector(selector, obj_type, indices)
        self._workplane = self._workplane.wires(selector, tag)
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None, type: Optional[CQGroupTypeString] = None, indices: Optional[Sequence[int]] = None):
        obj_type = type and self._type_groups[type]
        selector = CQExtensions.get_selector(selector, obj_type, indices)
        self._workplane = self._workplane.vertices(selector, tag)
        return self

    def vals(self):
        return self._entity_ctx.select_many(self._workplane)

    def val(self):
        return self._entity_ctx.select(self._workplane.val())


    def tag(self, names: Union[str, Sequence[str]]):
        if isinstance(names, str):
            self._workplane.tag(names)
        else:
            for i, cq_obj in enumerate(self._workplane.vals()):
                self._workplane.newObject([cq_obj]).tag(names[i])
        return self

    def fromTagged(self, tags: Union[str, Iterable[str]], resolve_type: Optional[CQType] = None, invert: bool = True):        
        if isinstance(tags, str) and resolve_type is None:
            self._workplane = self._workplane._getTagged(tags)
        else:
            tagged_objs = list(CQLinq.select_tagged(self._workplane, tags, resolve_type))
            tagged_cq_type = CQ_TYPE_STR_MAPPING[type(tagged_objs[0])]
            workplane_objs = CQLinq.select(self._workplane, tagged_cq_type)
            filtered_objs = CQLinq.filter(workplane_objs, tagged_objs, invert)
            self._workplane = self._workplane.newObject(filtered_objs)
        return self

    def addPhysicalGroup(self, group: Union[str, Sequence[str]]):
        if  isinstance(group, str):
            set_physical_group = SetPhysicalGroup(self.vals(), group)
            self._ctx.add_transaction(set_physical_group)
        else:
            objs = list(self.vals())
            group_entities: dict[str, OrderedSet[Entity]] = {}

            for i, group_name in enumerate(group):
                new_group_entity = objs[i]
                if group_name not in group_entities:
                    group_entities[group_name] = OrderedSet()
                group_entities[group_name].add(new_group_entity)
            
            for group_name, group_objs in group_entities.items():
                set_physical_group = SetPhysicalGroup(group_objs, group_name)
                self._ctx.add_transaction(set_physical_group)

        return self

    def recombine(self, angle: float = 45):
        faces = self._entity_ctx.select_many(self._workplane, "face")
        recombines = [Recombine(face, angle) for face in faces]
        self._ctx.add_transactions(recombines)
        return self

    def setMeshSize(self, size: Union[float, Callable[[float,float,float], float]]):
        points = self._entity_ctx.select_many(self._workplane, "vertex")
        set_size = SetMeshSize(points, size)
        self._ctx.add_transaction(set_size)
        return self

    def setMeshAlgorithm(self, type: MeshAlgorithm2DType, per_face: bool = False):
        faces = self._entity_ctx.select_many(self._workplane, "face")
        set_algorithms = [SetMeshAlgorithm2D(face, type, per_face) for face in faces]
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

    def setTransfiniteEdge(self, num_nodes: Union[Sequence[int], int], mesh_type: Union[TransfiniteMeshType, Sequence[TransfiniteMeshType]] = "Progression", coef: Union[float, Sequence[float]] = 1.0):
        edge_batch = self._entity_ctx.select_batch(self._workplane, "face", "edge")
        for edges in edge_batch:
            set_transfinite_edges = [SetTransfiniteEdge(
                edge, 
                num_nodes if isinstance(num_nodes, int) else num_nodes[i], 
                mesh_type if isinstance(mesh_type, str) else mesh_type[i], 
                coef if isinstance(coef, (int, float)) else coef[i]
            ) for i,edge in enumerate(edges)]
            self._ctx.add_transactions(set_transfinite_edges)

        return self

    def setTransfiniteFace(self, arrangement: TransfiniteArrangementType = "Left", corner_indexes: Sequence[int] = []):
        self.is_structured = True    
        cq_face_batch = CQLinq.select_batch(self._workplane, "solid", "face")
        for i, cq_faces in enumerate(cq_face_batch):
            faces = self._entity_ctx.select_many(cq_faces)
            set_transfinite_faces = [SetTransfiniteFace(face, arrangement) for face in faces]
            self._ctx.add_transactions(set_transfinite_faces)

        return self

    def setTransfiniteSolid(self):
        self.is_structured = True    
        solids = self._entity_ctx.select_many(self._workplane, "solid")
        set_transfinite_solids = [SetTransfiniteSolid(solid) for solid in solids]
        self._ctx.add_transactions(set_transfinite_solids)
        return self

    def _setTransfiniteFaceAuto(self, cq_faces: Sequence[cq.Face], num_nodes: int):
        self.is_structured = True    
        edge_transactions = []
        for cq_face in cq_faces:
            face = self._entity_ctx.select(cq_face)
            set_transfinite_face = SetTransfiniteFace(face)
            self._ctx.add_transaction(set_transfinite_face)
            for cq_edge in cq_face.Edges():
                edge = self._entity_ctx.select(cq_edge)
                set_transfinite_edge = SetTransfiniteEdge(edge, num_nodes)
                edge_transactions.append(set_transfinite_edge)
        self._ctx.add_transactions(edge_transactions, ignore_duplicates=True)


    def setTransfiniteAuto(self, num_nodes: int):
        self.is_structured = True
        if CQExtensions.get_dimension(self._workplane) == 2:
            cq_faces = cast(Sequence[cq.Face], CQLinq.select(self._workplane, "face"))
            self._setTransfiniteFaceAuto(cq_faces, num_nodes)
        else:
            for cq_solid in cast(Sequence[cq.Solid], CQLinq.select(self._workplane, "solid")):
                solid = self._entity_ctx.select(cq_solid)
                set_transfinite_solid = SetTransfiniteSolid(solid)
                self._setTransfiniteFaceAuto(cq_solid.Faces(), num_nodes)
                self._ctx.add_transaction(set_transfinite_solid)
        # transfinite_auto = SetTransfiniteAuto()
        # self._ctx.add_transaction(transfinite_auto)

        return self

    def _addStructuredBoundaryLayer(
            self, 
            cq_objs: Sequence[CQObject], 
            ratio: float = 1, 
            size: Optional[float] = None, 
            num_layers: Optional[int] = None, 
        ):
        assert self.is_structured, "Structured boundary layer can only be applied after setTransfiniteAuto"

        boundary_vertices =  list(CQLinq.select(cq_objs, "vertex"))

        for (cq_edge, edge) in self._entity_ctx.entity_registries["edge"].items():
            transaction = cast(SetTransfiniteEdge, self._ctx.get_transaction(SetTransfiniteEdge, edge))
            assert edge.type == "edge", "StructuredBoundaryLayer only accepts edges"
            num_elems = get_boundary_num_layers(cq_edge.Length(), ratio, size, num_layers) # type: ignore

            cq_curr_edge_vertices =  cq_edge.Vertices() # type: ignore
            if cq_curr_edge_vertices[0] in boundary_vertices and cq_curr_edge_vertices[-1] not in boundary_vertices:
                transaction.num_elems = num_elems
                transaction.coef = ratio

            elif cq_curr_edge_vertices[-1] in boundary_vertices and cq_curr_edge_vertices[0] not in boundary_vertices:
                transaction.num_elems = num_elems
                transaction.coef = -ratio

    def addBoundaryLayer(self, ratio: float = 1, size: Optional[float] = None, num_layers: Optional[int] = None):
        if self.is_structured:
            self._addStructuredBoundaryLayer(self._workplane.vals(), ratio, size, num_layers)
        else:
            assert num_layers is not None and size is not None and ratio is not None, "num_layers, hwall_n and ratio must be specified for unstructured boundary layer"
            if CQ_TYPE_RANKING[type(self._workplane.val())] < CQ_TYPE_RANKING[cq.Face]:
                boundary_layer = UnstructuredBoundaryLayer2D(self.vals(), ratio, size, num_layers)
            else:
                boundary_layer = UnstructuredBoundaryLayer(self.vals(), ratio, size, num_layers)
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

    def show(self, type: Literal["fltk", "mesh", "cq", "plot"] = "cq", only_markers: bool = False):
        if type == "fltk":
            gmsh.fltk.run()
        elif type == "mesh":
            assert self._ctx.mesh is not None, "Mesh is not generated yet."
            visualize_mesh(self._ctx.mesh, only_markers=only_markers)
        elif type == "plot":
            CQExtensions.plot_cq(self._workplane, ctx=self._entity_ctx)
        else:
            show(self._workplane, theme="dark")
        return self


    def close(self):
        gmsh.finalize()
