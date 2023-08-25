from dataclasses import dataclass
from plotly import graph_objects as go
import cadquery as cq
from cadquery.cq import CQObject, VectorLike
from typing import Iterable, Literal, Optional, Sequence, Union, cast
import numpy as np
from ezmesh.entity import EntityType
from ezmesh.utils.plot import add_plot
from ezmesh.utils.shapes import get_sampling
from ezmesh.utils.types import OrderedSet


@dataclass
class DirectedPath:
    edge: cq.Edge
    "edge of path"

    direction: int = 1
    "direction of path"

    def __post_init__(self):
        assert isinstance(self.edge, cq.Edge), "edge must be an edge"
        assert self.direction in [-1, 1], "direction must be -1 or 1"
        self.vertices = self.edge.Vertices()[::self.direction]
        self.start = self.vertices[0]
        self.end = self.vertices[-1]

CQGroupTypeString = Literal["split", "interior", "exterior"]


class CQLinq:
    @staticmethod
    def is_interior_face(face: CQObject, invert: bool = False):
        assert isinstance(face, cq.Face), "object must be a face"
        face_normal = face.normalAt()
        face_centroid = face.Center()
        interior_dot_product = face_normal.dot(face_centroid)
        return (not invert and interior_dot_product < 0) or (invert and interior_dot_product >= 0)

    @staticmethod
    def select_tagged(workplane: cq.Workplane, tags: Union[str, Iterable[str]], type: EntityType):
        for tag in ([tags] if isinstance(tags, str) else tags):
            yield from CQLinq.select(workplane._getTagged(tag).vals(), type)

    @staticmethod
    def get_entity_type(shape: CQObject):
        if isinstance(shape, cq.Compound): 
            return EntityType.compound
        if isinstance(shape, cq.Solid): 
            return EntityType.solid
        if isinstance(shape, cq.Shell): 
            return EntityType.shell
        elif isinstance(shape, cq.Face):
            return EntityType.face
        elif isinstance(shape, cq.Wire):
            return EntityType.wire
        elif isinstance(shape, cq.Edge):
            return EntityType.edge
        elif isinstance(shape, cq.Vertex):
            return EntityType.vertex
        else:
            raise NotImplementedError(f"shape {shape} not supported")
    
    @staticmethod
    def select(target: Union[cq.Workplane, Iterable[CQObject], CQObject], type: EntityType):
        cq_objs = target.vals() if isinstance(target, cq.Workplane) else (target if isinstance(target, Iterable) else [target])
        for occ_obj in cq_objs:
            assert isinstance(occ_obj, cq.Shape), "target must be a shape"
            if type == EntityType.compound:
                yield from occ_obj.Compounds()
            if type == EntityType.solid:
                yield from occ_obj.Solids()
            elif type == EntityType.shell:
                yield from occ_obj.Shells()
            elif type == EntityType.face:
                yield from occ_obj.Faces()
            elif type == EntityType.wire:
                yield from occ_obj.Wires()
            elif type == EntityType.edge:
                yield from occ_obj.Edges()
            elif type == EntityType.vertex:
                yield from occ_obj.Vertices()

    @staticmethod
    def select_batch(target: Union[cq.Workplane, Iterable[CQObject]], parent_type: EntityType, child_type: EntityType):
        cq_objs = list(target.vals() if isinstance(target, cq.Workplane) else target)
        entity_type = CQLinq.get_entity_type(cq_objs[0])
        if entity_type.value == child_type.value:
            yield cq_objs
        else:
            parent_cq_objs = CQLinq.select(cq_objs, parent_type)
            for parent_occ_obj in parent_cq_objs:
                yield CQLinq.select([parent_occ_obj], child_type)

    @staticmethod
    def filter(objs: Iterable[CQObject], filter_objs: Iterable[CQObject], invert: bool):
        filter_objs = set(filter_objs)
        for occ_obj in objs:
            if (invert and occ_obj in filter_objs) or (not invert and occ_obj not in filter_objs):
                yield occ_obj

    @staticmethod
    def sort(target: Union[CQObject, Sequence[CQObject]]):
        unsorted_edges = cast(list[cq.Edge], list(CQLinq.select(target, EntityType.edge)))
        edges = list(unsorted_edges[1:])
        sorted_paths = [DirectedPath(unsorted_edges[0])]
        while edges:
            for i, edge in enumerate(edges):
                vertices = edge.Vertices()
                if vertices[0].toTuple() == sorted_paths[-1].end.toTuple():
                    sorted_paths.append(DirectedPath(edge))
                    edges.pop(i)
                    break
                elif vertices[-1].toTuple() == sorted_paths[-1].end.toTuple():
                    sorted_paths.append(DirectedPath(edge, direction=-1))
                    edges.pop(i)
                    break
                elif vertices[0].toTuple() == sorted_paths[0].start.toTuple():
                    sorted_paths.insert(0, DirectedPath(edge, direction=-1))
                    edges.pop(i)
                    break
            else:
                raise ValueError("Edges do not form a closed loop")
        
        return sorted_paths
    
    @staticmethod
    def _add_to_group(
        wires: Iterable[cq.Wire],
        registry: OrderedSet[CQObject],
    ):
        for wire in wires:
            registry.add(wire)
            for edge in wire.Edges():
                registry.add(edge)
            for vertex in wire.Vertices():
                registry.add(vertex)

    @staticmethod
    def group(
        target: Union[cq.Workplane, Sequence[CQObject]], 
        split_faces: Optional[OrderedSet[CQObject]] = None
    ):
        groups: dict[CQGroupTypeString, OrderedSet[CQObject]] = {
            "split": OrderedSet[CQObject](),
            "interior": OrderedSet[CQObject](),
            "exterior": OrderedSet[CQObject](),
        }
        faces = list(CQLinq.select(target, EntityType.face))
        if len(faces) > 0:
            for face in faces:
                assert isinstance(face, cq.Face), "object must be a face"
                if split_faces and face in split_faces:
                    face_registry = groups["split"]
                else:
                    interior_face = CQLinq.is_interior_face(face) 
                    face_registry = groups["interior" if interior_face else "exterior"]
                face_registry.add(face)
                CQLinq._add_to_group(face.Wires(), face_registry)
        else:
            CQLinq._add_to_group(faces[0].innerWires(), groups["interior"])
            CQLinq._add_to_group([faces[0].outerWire()], groups["exterior"])

        return groups

class CQExtensions:
    @staticmethod
    def find_nearest_point(workplane: cq.Workplane, near_point: cq.Vertex, tolerance: float = 1e-2):
        min_dist_vertex, min_dist = None, float("inf")
        for vertex in workplane.vertices().vals():
            dist = vertex.distance(near_point)
            if dist < min_dist and dist <= tolerance:
                min_dist_vertex, min_dist = vertex, dist
        return min_dist_vertex

    @staticmethod
    def split_intersect(workplane: cq.Workplane, anchor: VectorLike, splitter: cq.Face, snap_tolerance: Optional[float] = None):
        intersected_vertices = workplane.intersect(cq.Workplane(splitter)).vertices().vals()
        min_dist_vertex, min_dist = None, float("inf") 
        for vertex in intersected_vertices:
            try:
                to_intersect_line = cq.Edge.makeLine(anchor, vertex.toTuple()) # type: ignore
                intersect_dist = to_intersect_line.Length() # type: ignore
                if intersect_dist < min_dist:
                    min_dist_vertex, min_dist = vertex, intersect_dist
            except: ...
        assert isinstance(min_dist_vertex, cq.Vertex), "No intersected vertex found"
        if snap_tolerance:
            nearest_point = CQExtensions.find_nearest_point(workplane, min_dist_vertex, snap_tolerance)
            if nearest_point:
                return nearest_point
        return min_dist_vertex

    @staticmethod
    def plot_groups(
        groups: Sequence[Sequence[CQObject]], 
        title: str = "Group Plot", 
        samples_per_spline: int = 50,
    ):
        fig = go.Figure(
            layout=go.Layout(title=go.layout.Title(text=title))
        )
        for i, group in enumerate(groups):
            group_coords = []
            sampling = get_sampling(0, 1, samples_per_spline, False)
            for edge in group:
                group_coords += [vec.toTuple() for vec in edge.positions(sampling)]
            add_plot(np.array(group_coords), fig, f"Group {i}")

        fig.layout.yaxis.scaleanchor = "x"  # type: ignore
        fig.show()
