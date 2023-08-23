from dataclasses import dataclass
import cadquery as cq
import numpy as np
from plotly import graph_objects as go
from cadquery.cq import CQObject, VectorLike
from typing import Iterable, Optional, OrderedDict, Sequence, Union, cast
from ezmesh.entity import Entity, EntityType
from ezmesh.utils.cq import CQRegistry, CQUtils, get_cq_registry
from ezmesh.utils.plot import add_plot
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import OrderedSet


class CQEntityContext:
    "Maps OCC objects to gmsh entity tags"
    def __init__(self, workplane: cq.Workplane, partition_faces: Optional[OrderedSet[CQObject]] = None) -> None:
        self.dimension = 2 if isinstance(workplane.val(), cq.Face) else 3

        self.entity_registries: dict[EntityType, OrderedDict[CQObject, Entity]] = {
            EntityType.solid: OrderedDict[CQObject, Entity](),
            EntityType.shell: OrderedDict[CQObject, Entity](),
            EntityType.face:  OrderedDict[CQObject, Entity](),
            EntityType.wire: OrderedDict[CQObject, Entity](),
            EntityType.edge: OrderedDict[CQObject, Entity](),
            EntityType.vertex: OrderedDict[CQObject, Entity](),
        }

        if self.dimension == 3:
            self._init_3d_objs(workplane)
        else:
            self._init_2d_objs(workplane)

        self.cq_registry = get_cq_registry(workplane, partition_faces)

    def add(self, obj: CQObject):
        entity_type = CQUtils.get_entity_type(obj)
        registry = self.entity_registries[entity_type]
        if obj not in registry:
            tag = len(registry) + 1
            registry[obj] = Entity(entity_type, tag)


    def select(self, obj: CQObject):
        entity_type = CQUtils.get_entity_type(obj)
        registry = self.entity_registries[entity_type]
        return registry[obj]
    
    def select_many(self, target: Union[cq.Workplane, Iterable[CQObject]], type: Optional[EntityType] = None):
        entities = OrderedSet[Entity]()
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_objs = objs if type is None else CQUtils.select(objs, type)
        for obj in selected_objs:
            try:
                selected_entity = self.select(obj)
                entities.add(selected_entity)
            except:
                ...

        return entities
    
    def select_batch(self, target: Union[cq.Workplane, Iterable[CQObject]], parent_type: EntityType, child_type: EntityType):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_batches = CQUtils.select_batch(objs, parent_type, child_type)
        for selected_batch in selected_batches:
            yield self.select_many(selected_batch)

    def _init_3d_objs(self, target: Union[cq.Workplane, Sequence[CQObject]]):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        for compound in cast(Sequence[cq.Solid], objs):
            for solid in compound.Solids():
                for shell in solid.Shells():
                    self._init_2d_objs(shell.Faces())
                    self.add(shell)
                self.add(solid)

    def _init_2d_objs(self, target: Union[cq.Workplane, Sequence[CQObject]]):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        for face in cast(Sequence[cq.Face], objs):
            for wire in [face.outerWire(), *face.innerWires()]:
                for edge in wire.Edges():
                    for vertex in edge.Vertices():
                        self.add(vertex)
                    self.add(edge)
                self.add(wire)
            self.add(face)

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
        for path in CQUtils.sort(face):
            if path.start in partition_vertices or len(edge_groups) == 0:
                edge_groups.append([])
            edge_groups[-1].append(path.edge)
        face_groups[face] = edge_groups
    return PartitionResult(workplane, partition_faces, face_groups)

# def reassmble_workplane(workplane: cq.Workplane, partitions: Sequence[Partition]):
    


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

def tag_workplane(workplane: cq.Workplane, ctx: CQEntityContext):
    "Tag all gmsh entity tags to workplane"
    for registry_name, registry in ctx.entity_registries.items():
        for occ_obj in registry.keys():
            tag = f"{registry_name.name}/{registry[occ_obj].tag}"
            workplane.newObject([occ_obj]).tag(tag)

def plot_workplane(
    target: Union[cq.Workplane, Iterable[CQObject]], 
    ctx: CQEntityContext,
    title: str = "Plot", 
    samples_per_spline: int = 50,
):
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    edges = CQUtils.select(target, EntityType.edge)
    registry = ctx.entity_registries[EntityType.edge]
    for edge in edges:
        edge_entity = registry[edge]
        edge_name = registry[edge].name or f"Edge{edge_entity.tag}"
        sampling = get_sampling(0, 1, samples_per_spline, False)
        coords = np.array([vec.toTuple() for vec in edge.positions(sampling)], dtype=NumpyFloat) # type: ignore
        add_plot(coords, fig, edge_name)

    fig.layout.yaxis.scaleanchor = "x"  # type: ignore
    fig.show()


class IndexSelector(cq.Selector):
    def __init__(self, indices: Sequence[int]):
        self.indices = indices
    def filter(self, objectList):
        return [objectList[i] for i in self.indices]

class InteriorSelector(cq.Selector):
    def __init__(self, index: CQRegistry, is_interior: bool = True):
        self.index = index
        self.is_interior = is_interior
    def filter(self, objectList):
        filtered_objs = []
        for obj in objectList:
            if (self.is_interior and obj in self.index.interior) or (not self.is_interior and obj in self.index.exterior):
                filtered_objs.append(obj)
        return filtered_objs

def get_selector(registry: CQRegistry, selector: Union[cq.Selector, str, None], indices: Optional[Sequence[int]] = None, is_interior: Optional[bool] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(cq.StringSyntaxSelector(selector))
    elif isinstance(selector, cq.Selector):
        selectors.append(selector)

    if is_interior is not None:
        selectors.append(InteriorSelector(registry, is_interior))
    if indices is not None:
        selectors.append(IndexSelector(indices))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = cq.selectors.AndSelector(prev_selector, selector)
        return prev_selector





