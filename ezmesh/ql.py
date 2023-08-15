import gmsh
import cadquery as cq
from cadquery.cq import CQObject
from typing import Callable, Iterable, Literal, Optional, Union
from cadquery.selectors import Selector
from ezmesh.mesh.exporters import export_to_su2
from ezmesh.occ import EntityType
from ezmesh.transactions.algorithm import MeshAlgorithm2DType, SetMeshAlgorithm
from ezmesh.transactions.boundary_layer import BoundaryLayer
from ezmesh.transactions.refinement import Recombine, Refine, SetSize
from ezmesh.utils.cq import OCCMap, filter_occ_objs, get_selector, get_tagged_occ_objs, import_workplane, select_occ_type, tag_entities
from ezmesh.transactions.transaction import TransactionContext
from jupyter_cadquery import show
from ezmesh.visualizer import visualize_mesh

class GeometryQL:
    _workplane: cq.Workplane
    _initial_workplane: cq.Workplane
    def __init__(self) -> None:
        self._initial_workplane = self._workplane = None # type: ignore
        self._ctx = TransactionContext()

    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def end(self):
        self._workplane = self._initial_workplane
        return self
    
    def load(self, target: Union[cq.Workplane, str, Iterable[CQObject]]):
        assert self._workplane is None, "Workplane is already loaded."

        self._initial_workplane = self._workplane = import_workplane(target)

        topods = self._workplane.toOCC()
        gmsh.model.occ.importShapesNativePointer(topods._address())
        gmsh.model.occ.synchronize()
        self._occ_map = OCCMap(self._workplane)

        tag_entities(self._workplane, self._occ_map)
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

    def vals(self):
        return list(self._occ_map.select_entities(self._workplane.vals()))

    def tag(self, name: str):
        self._workplane = self._workplane.tag(name)
        return self

    def fromTagged(self, tag: Union[str, Iterable[str]], type: Optional[EntityType] = None, is_included: bool = True):        
        if isinstance(tag, str) and type is None:
            self._workplane = self._workplane._getTagged(tag)
        elif type is not None:
            occ_tagged_objs = get_tagged_occ_objs(self._workplane, tag, type)
            occ_selected_objs = select_occ_type(self._workplane, type)
            occ_filtered_objs = list(filter_occ_objs(occ_selected_objs, occ_tagged_objs, is_included))
            self._workplane = self._workplane.newObject(occ_filtered_objs)

        return self

    def addPhysicalGroup(self, name: str, tagWorkspace: bool = True):
        self._ctx.add_physical_groups(name, self.vals())
        if tagWorkspace:
            self.tag(name)
        return self

    def recombine(self, angle: float = 45):
        surfaces = self._occ_map.select_entities(self._workplane.vals(), "face")
        recombine = Recombine(surfaces, angle)
        self._ctx.add_transaction(recombine)
        return self

    def refine(self, num_refines = 1):
        refine = Refine(num_refines)
        self._ctx.add_transaction(refine)
        return self

    def setMeshSize(self, size: Union[float, Callable[[float,float,float], float]]):
        points = self._occ_map.select_entities(self._workplane.vals(), "vertex")
        set_size = SetSize(points, size)
        self._ctx.add_transaction(set_size)
        return self

    def setAlgorithm(self, type: MeshAlgorithm2DType):
        set_algorithm = SetMeshAlgorithm(self.vals(), type)
        self._ctx.add_transaction(set_algorithm)
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
            ...
            # plot_entities(self.vals())
        else:
            show(self._workplane)
        return self


    def close(self):
        gmsh.finalize()
