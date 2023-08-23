from dataclasses import dataclass
import cadquery as cq
from cadquery.cq import CQObject
from typing import Iterable, Optional, Sequence, Union, cast
from ezmesh.entity import EntityType
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

@dataclass
class CQRegistry:
    interior = OrderedSet[CQObject]()
    exterior = OrderedSet[CQObject]()

class CQUtils:
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
            yield from CQUtils.select(workplane._getTagged(tag).vals(), type)

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
        entity_type = CQUtils.get_entity_type(cq_objs[0])
        if entity_type.value == child_type.value:
            yield cq_objs
        else:
            parent_cq_objs = CQUtils.select(cq_objs, parent_type)
            for parent_occ_obj in parent_cq_objs:
                yield CQUtils.select([parent_occ_obj], child_type)

    @staticmethod
    def filter(objs: Iterable[CQObject], filter_objs: Iterable[CQObject], invert: bool):
        filter_objs = set(filter_objs)
        for occ_obj in objs:
            if (invert and occ_obj in filter_objs) or (not invert and occ_obj not in filter_objs):
                yield occ_obj

    @staticmethod
    def sort(target: Union[CQObject, Sequence[CQObject]]):
        unsorted_edges = cast(Sequence[cq.Edge], list(CQUtils.select(target, EntityType.edge)))
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
    


def get_cq_registry(
    target: Union[cq.Workplane, Sequence[CQObject]], 
    partition_faces: Optional[OrderedSet[CQObject]] = None
):
    index = CQRegistry()

    faces = list(CQUtils.select(target, EntityType.face))
    if len(faces) > 0:
        for face in faces:
            if partition_faces and face in partition_faces:
                continue
            assert isinstance(face, cq.Face), "object must be a face"
            interior_face = CQUtils.is_interior_face(face) 
            if interior_face:
                index.interior.add(face)
            else:
                index.exterior.add(face)

            for wire in face.innerWires():
                add_wire_to_registry(index, wire)

            add_wire_to_registry(index, face.outerWire(), is_interior=False)
    return index

def add_wire_to_registry(
    index: CQRegistry,
    wire: cq.Wire,
    is_interior: bool = True
):
    curr_index = index.interior if is_interior else index.exterior
    opposite_index = index.exterior if is_interior else index.interior

    curr_index.add(wire)
    for edge in wire.Edges():
        if edge not in opposite_index:
            curr_index.add(edge)
    for vertex in wire.Vertices():
        if vertex not in opposite_index:
            curr_index.add(vertex)