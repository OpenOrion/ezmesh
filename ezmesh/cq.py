from dataclasses import dataclass
import cadquery as cq
import numpy as np
from plotly import graph_objects as go
from cadquery.cq import CQObject
from typing import Iterable, Literal, Optional, OrderedDict, Sequence, Union, cast
from ezmesh.entity import Entity, EntityType
from ezmesh.utils.cq import CQExtensions, CQLinq
from ezmesh.utils.plot import add_plot
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import OrderedSet
from jupyter_cadquery import show_object
from ezmesh.utils.types import NumpyFloat

class CQEntityContext:
    "Maps OCC objects to gmsh entity tags"
    def __init__(self, workplane: cq.Workplane) -> None:
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

    def add(self, obj: CQObject):
        entity_type = CQLinq.get_entity_type(obj)
        registry = self.entity_registries[entity_type]
        if obj not in registry:
            tag = len(registry) + 1
            registry[obj] = Entity(entity_type, tag)


    def select(self, obj: CQObject):
        entity_type = CQLinq.get_entity_type(obj)
        registry = self.entity_registries[entity_type]
        return registry[obj]
    
    def select_many(self, target: Union[cq.Workplane, Iterable[CQObject]], type: Optional[EntityType] = None):
        entities = OrderedSet[Entity]()
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_objs = objs if type is None else CQLinq.select(objs, type)
        for obj in selected_objs:
            try:
                selected_entity = self.select(obj)
                entities.add(selected_entity)
            except:
                ...

        return entities
    
    def select_batch(self, target: Union[cq.Workplane, Iterable[CQObject]], parent_type: EntityType, child_type: EntityType):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_batches = CQLinq.select_batch(objs, parent_type, child_type)
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

VectorTuple = tuple[float, float, float]
EdgeTuple = tuple[VectorTuple, VectorTuple]
class Split:
    @staticmethod
    def from_plane(
        workplane: cq.Workplane,
        base_pnt: VectorTuple = (0,0,0), 
        angle: VectorTuple = (0,0,0), 
    ):
        return cq.Face.makePlane(None, None, tuple(base_pnt), tuple(np.radians(angle)))

    @staticmethod
    def from_anchor(
        workplane: cq.Workplane, 
        anchor: Union[list[VectorTuple], VectorTuple] = (0,0,0), 
        angle: Union[list[VectorTuple], VectorTuple] = (0,0,0),
        snap_tolerance: Optional[float] = None
    ):
        anchors = [anchor] if isinstance(anchor, tuple) else anchor
        angles = [angle] if isinstance(angle, tuple) else angle
        assert len(anchors) == len(angles), "anchors and angles must be the same length"

        edges = []
        for anchor, angle in zip(anchors, angles):
            split_face = Split.from_plane(workplane, anchor, angle)
            intersect_vertex = CQExtensions.split_intersect(workplane, anchor, split_face, snap_tolerance)
            workplane.newObject
            edges.append((anchor, intersect_vertex.toTuple()))
        return Split.from_edges(workplane, edges)
    
    @staticmethod
    def from_pnts(workplane: cq.Workplane, pnts: Sequence[tuple[float, float, float]]):
        return cq.Face.makeFromWires(cq.Wire.makePolygon(pnts))

    @staticmethod
    def from_edges(
        workplane: cq.Workplane, 
        edges: Union[list[EdgeTuple], EdgeTuple], 
        dir: Literal["X", "Y", "Z"] = "Z"
    ):
        edges_pnts = np.array([edges] if isinstance(edges, tuple) else edges)
        if len(edges_pnts) == 1:
            top_pnts = edges_pnts[0]
            maxDim = workplane.findSolid().BoundingBox().DiagonalLength * 10.0
            bottom_pnts = np.array(top_pnts)
            bottom_pnts[:, {"X": 0, "Y": 1, "Z": 2}[dir]] = -maxDim

            return Split.from_pnts(workplane, [*top_pnts.tolist(), *bottom_pnts[::-1].tolist()])

        return Split.from_pnts(workplane, [*edges_pnts[:,0].tolist(),*edges_pnts[:,1][::-1].tolist()])



def split_workplane(workplane: cq.Workplane, splits: Sequence[cq.Face]):
    for split in splits:      
        workplane = workplane.split(split)
    return workplane

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
    ctx: Optional[CQEntityContext] = None,
    title: str = "Plot", 
    samples_per_spline: int = 50,
):
    fig = go.Figure(
        layout=go.Layout(title=go.layout.Title(text=title))
    )
    edges = CQLinq.select(target, EntityType.edge)
    registry = ctx.entity_registries[EntityType.edge] if ctx else None
    for edge in edges:
        edge_name = (registry[edge].name or f"Edge{registry[edge].tag}") if registry else "Edge"
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

class GroupSelector(cq.Selector):
    def __init__(self, allow: OrderedSet[CQObject], is_interior: bool = True):
        self.allow = allow
        self.is_interior = is_interior
    def filter(self, objectList):
        filtered_objs = []
        for obj in objectList:
            if obj in self.allow:
                filtered_objs.append(obj)
        return filtered_objs

def get_selector(selector: Union[cq.Selector, str, None], group: Optional[OrderedSet[CQObject]], indices: Optional[Sequence[int]] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(cq.StringSyntaxSelector(selector))
    elif isinstance(selector, cq.Selector):
        selectors.append(selector)

    if group is not None:
        selectors.append(GroupSelector(group))
    if indices is not None:
        selectors.append(IndexSelector(indices))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = cq.selectors.AndSelector(prev_selector, selector)
        return prev_selector

