from dataclasses import dataclass
import cadquery as cq
import numpy as np
from cadquery.cq import CQObject, VectorLike
from typing import Iterable, Optional, Sequence, Union
from plotly import graph_objects as go
from ezmesh.occ import EntityType, OCCMap, get_sorted_paths, select_occ_objs
from ezmesh.utils.plot import add_plot
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import NumpyFloat, OrderedSet
from OCP.BRep import BRep_Tool
from jupyter_cadquery import show_object 

@dataclass
class Partition:
    base_point: VectorLike = (0,0,0)
    "base point of the plane"

    angles: VectorLike = (0,0,0)
    "angle of plane"

@dataclass
class PartitionResult:
    workplane: cq.Workplane
    "partitioned workplane"

    faces: OrderedSet[CQObject]
    "partition intersected faces"

    groups: dict[CQObject, list[list[CQObject]]]
    "groups of face edge groups"

@dataclass
class EdgeGroup:
    edge: CQObject
    "edge"



class IndexSelector(cq.Selector):
    def __init__(self, indices: Sequence[int]):
        self.indices = indices
    def filter(self, objectList):
        return [objectList[i] for i in self.indices]

class InteriorSelector(cq.Selector):
    def __init__(self, occ_map: OCCMap, is_interior: bool = True):
        self.occ_map = occ_map
        self.is_interior = is_interior
    def filter(self, objectList):
        filtered_objs = []
        for obj in objectList:
            if (self.is_interior and obj in self.occ_map.interior) or (not self.is_interior and obj in self.occ_map.exterior):
                filtered_objs.append(obj)
        return filtered_objs

def get_selector(occ_map: OCCMap, selector: Union[cq.Selector, str, None], indices: Optional[Sequence[int]] = None, is_interior: Optional[bool] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(cq.StringSyntaxSelector(selector))
    elif isinstance(selector, cq.Selector):
        selectors.append(selector)

    if is_interior is not None:
        selectors.append(InteriorSelector(occ_map, is_interior))
    if indices is not None:
        selectors.append(IndexSelector(indices))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = cq.selectors.AndSelector(prev_selector, selector)
        return prev_selector


def partition_workplane(workplane: cq.Workplane, partitions: Sequence[Partition]):
    partition_faces = OrderedSet[CQObject]()
    partition_vertices = OrderedSet[CQObject]()

    for partition in partitions:
        angles_deg = (partition.angles.toTuple() if isinstance(partition.angles, cq.Vector) else partition.angles)
        plane = cq.Face.makePlane(
            None,
            None,
            cq.Vector(partition.base_point), 
            cq.Vector(tuple(np.radians(angles_deg)))
        )
        workplane = workplane.split(plane)
        intersected_worplane = workplane.intersect(cq.Workplane(plane))
        partition_faces.update(intersected_worplane.faces().vals())
        partition_vertices.update(intersected_worplane.vertices().vals())
    
    face_groups = dict[CQObject, list[list[CQObject]]]()
    for face in workplane.faces().vals():
        edge_groups: list[list[CQObject]] = []
        for path in get_sorted_paths(face):
            if path.start in partition_vertices:
                edge_groups.append([])
            edge_groups[-1].append(path.edge)
        face_groups[face] = edge_groups
    return PartitionResult(workplane, partition_faces, face_groups)


def get_plane(face: cq.Face):
    origin = face.Center()
    normal = face.normalAt()
    x_dir = cq.Vector(0, 0, 1).cross(normal)
    if x_dir.Length == 0:
        x_dir = cq.Vector(
            BRep_Tool.Surface_s(face.wrapped).Position().XDirection()
        )
    return cq.Plane(origin, x_dir, normal)

def import_workplane(target: Union[cq.Workplane, str, Iterable[CQObject]]):
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

    workplane.tag("root")

    return workplane

def tag_workplane_entities(workplane: cq.Workplane, occ_map: OCCMap):
    "Tag all gmsh entity tags to workplane"
    for registry_name, registry in occ_map.registries.items():
        for occ_obj in registry.entities.keys():
            tag = f"{registry_name.name}/{registry.entities[occ_obj].tag}"
            workplane.newObject([occ_obj]).tag(tag)


def plot_cq(
    target: Union[cq.Workplane, Iterable[CQObject]], 
    occ_map: OCCMap,
    title: str = "Plot", 
    samples_per_spline: int = 50,
):
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    edges = select_occ_objs(target, EntityType.edge)
    registry = occ_map.registries[EntityType.edge]
    for edge in edges:
        edge_entity = registry.entities[edge]
        edge_name = registry.entities[edge].name or f"Edge{edge_entity.tag}"
        sampling = get_sampling(0, 1, samples_per_spline, False)
        coords = np.array([vec.toTuple() for vec in edge.positions(sampling)], dtype=NumpyFloat) # type: ignore
        add_plot(coords, fig, edge_name)

    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()

