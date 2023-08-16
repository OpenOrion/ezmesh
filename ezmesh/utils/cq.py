from dataclasses import dataclass
import cadquery as cq
import numpy as np
from cadquery.cq import CQObject, VectorLike
from typing import Iterable, Optional, Sequence, Union, cast
from plotly import graph_objects as go
from ezmesh.occ import EntityType, OCCMap, select_occ_objs
from ezmesh.utils.plot import add_plot
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import NumpyFloat
from jupyter_cadquery import show

@dataclass
class Region:
    point: VectorLike = (0,0,0)
    "base point of the plane"
    
    angles: VectorLike = (0,0,0)
    "angle of plane"


class InteriorSelector(cq.Selector):
    def __init__(self, workplane: cq.Workplane, is_interior: bool = True):
        self.workplane = workplane
        self.is_interior = is_interior
    def filter(self, objectList):
        parent_objects = self.workplane.vals()
        if len(parent_objects) == 1 and isinstance(parent_objects[0], cq.Face): 
            return InteriorSelector.get_interior_edges(objectList[0], parent_objects[0], self.is_interior)
        return filter(lambda object: self.is_interior == InteriorSelector.get_interior_face(object), objectList)

    @staticmethod
    def get_interior_face(object: cq.Face):
        face_normal = object.normalAt()
        face_centroid = object.Center()
        interior_dot_product = face_normal.dot(face_centroid)
        return interior_dot_product < 0

    @staticmethod
    def get_interior_edges(object: Union[cq.Face, cq.Wire], parent: cq.Face, is_interior: bool):
        wires = parent.innerWires() if is_interior else [parent.outerWire()]
        if isinstance(object, cq.Wire): 
            return wires
        elif isinstance(object, cq.Edge):
            return [edge for  wire in wires for edge in wire.Edges()]

def get_selector(workplane: cq.Workplane, selector: Union[cq.Selector, str, None], is_interior: Optional[bool] = None, index: Optional[int] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(cq.StringSyntaxSelector(selector))
    elif isinstance(selector, cq.Selector):
        selectors.append(selector)

    if is_interior is not None:
        selectors.append(InteriorSelector(workplane, is_interior))
    if index is not None:
        selectors.append(cq.selectors.AreaNthSelector(index))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = cq.selectors.AndSelector(prev_selector, selector)
        return prev_selector

def split_worplane_regions(workplane: cq.Workplane, regions: Sequence[Region]):
    for region in regions:
        angles_deg = (region.angles.toTuple() if isinstance(region.angles, cq.Vector) else region.angles)
        workplane = workplane.split(cq.Face.makePlane(
            None,
            None,
            cq.Vector(region.point), 
            cq.Vector(tuple(np.radians(angles_deg)))
        ))
            
    return workplane


def import_workplane(target: Union[cq.Workplane, str, Iterable[CQObject]], regions: Optional[Sequence[Region]] = None):
    if isinstance(target, str):
        if target.lower().endswith(".step"):
            workplane = cq.importers.importStep(target)
        elif target.lower().endswith(".dxf"):
            workplane = cq.importers.importDXF(target)
        else:
            raise ValueError(f"Unsupported file type: {target}")
    elif isinstance(target, Iterable):
        workplane = cq.Workplane().newObject(target)
    else:
        workplane = target
    if isinstance(workplane.val(), cq.Wire):
        workplane = cq.Workplane().newObject(workplane.extrude(-1).faces(">Z").vals())

    if regions:
        workplane = split_worplane_regions(workplane, regions)

    return workplane

def tag_workplane_entities(workplane: cq.Workplane, occ_map: OCCMap):
    "Tag all gmsh entity tags to workplane"
    for registry_name, registry in occ_map.registries.items():
        for occ_obj in registry.entities.keys():
            tag = f"{registry_name}/{registry.entities[occ_obj].tag}"
            workplane.newObject([occ_obj]).tag(tag)


def plot_workplane(
    workplane: cq.Workplane, 
    occ_map: OCCMap,
    title: str = "Plot", 
    samples_per_spline: int = 50,
):
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    edges = select_occ_objs(workplane, "edge")
    registry = occ_map.registries["edge"]
    for edge in edges:
        edge_entity = registry.entities[edge]
        edge_name = registry.entities[edge].name or f"Edge{edge_entity.tag}"
        sampling = get_sampling(0, 1, samples_per_spline, False)
        coords = np.array([vec.toTuple() for vec in edge.positions(sampling)], dtype=NumpyFloat) # type: ignore
        add_plot(coords, fig, edge_name)

    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()

