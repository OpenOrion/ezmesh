from dataclasses import dataclass
import cadquery as cq
from cadquery.cq import CQObject
from cadquery.occ_impl.shapes import TopAbs_Orientation
from typing import Iterable, Optional, OrderedDict, Sequence, Union, cast
from ezmesh.entity import Entity, EntityType
from ezmesh.utils.types import OrderedSet

def get_is_face_reversed(face: CQObject):
    assert isinstance(face, cq.Face), "object must be a face"
    return face.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED

def select_tagged_occ_objs(workplane: cq.Workplane, tags: Union[str, Iterable[str]], type: EntityType):
    for tag in ([tags] if isinstance(tags, str) else tags):
        yield from select_occ_objs(workplane._getTagged(tag).vals(), type)

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

def select_occ_objs(target: Union[cq.Workplane, Iterable[CQObject], CQObject], type: EntityType):
    occ_objs = target.vals() if isinstance(target, cq.Workplane) else (target if isinstance(target, Iterable) else [target])
    for occ_obj in occ_objs:
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


def select_batch_occ_objs(target: Union[cq.Workplane, Iterable[CQObject]], parent_type: EntityType, child_type: EntityType):
    occ_objs = list(target.vals() if isinstance(target, cq.Workplane) else target)
    entity_type = get_entity_type(occ_objs[0])
    if entity_type.value == child_type.value:
        yield occ_objs
    else:
        parent_occ_objs = select_occ_objs(occ_objs, parent_type)
        for parent_occ_obj in parent_occ_objs:
            yield select_occ_objs([parent_occ_obj], child_type)

def filter_occ_objs(occ_objs: Iterable[CQObject], filter_objs: Iterable[CQObject], invert: bool):
    filter_objs = set(filter_objs)
    for occ_obj in occ_objs:
        if (invert and occ_obj in filter_objs) or (not invert and occ_obj not in filter_objs):
            yield occ_obj


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

def get_sorted_paths(target: Union[CQObject, Sequence[CQObject]]):
    unsorted_edges = cast(Sequence[cq.Edge], list(select_occ_objs(target, EntityType.edge)))
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
 

def is_interior_face(face: CQObject, invert: bool = False):
    assert isinstance(face, cq.Face), "object must be a face"
    face_normal = face.normalAt()
    face_centroid = face.Center()
    interior_dot_product = face_normal.dot(face_centroid)
    return (not invert and interior_dot_product < 0) or (invert and interior_dot_product >= 0)

class OCCRegistry:
    def __init__(self) -> None:
        self.entities = OrderedDict[CQObject, Entity]()
class OCCMap:
    "Maps OCC objects to gmsh tags"
    def __init__(self, workplane: cq.Workplane, partition_faces: Optional[OrderedSet[CQObject]] = None) -> None:
        self.dimension = 2 if isinstance(workplane.val(), cq.Face) else 3
        self.interior = OrderedSet[CQObject]()
        self.exterior = OrderedSet[CQObject]()

        self.registries: dict[EntityType, OCCRegistry] = {
            EntityType.solid: OCCRegistry(),
            EntityType.shell: OCCRegistry(),
            EntityType.face:  OCCRegistry(),
            EntityType.wire: OCCRegistry(),
            EntityType.edge: OCCRegistry(),
            EntityType.vertex: OCCRegistry(),
        }

        if self.dimension == 3:
            self.init_3d_objs(workplane)
        else:
            self.init_2d_objs(workplane)

        faces = list(select_occ_objs(workplane, EntityType.face))
        if len(faces) > 0:
            for face in faces:
                if partition_faces and face in partition_faces:
                    continue
                assert isinstance(face, cq.Face), "object must be a face"
                interior_face = is_interior_face(face) 
                if interior_face:
                    self.add_interior_face(face)
                else:
                    self.add_interior_face(face, invert=True)

                for occ_wire in face.innerWires():
                    self.add_interior_wire(occ_wire)

                self.add_interior_wire(face.outerWire(), invert=not interior_face)

    def add_interior_face(self, face: cq.Face, invert: bool = False):
        interior_idx = self.interior if not invert else self.exterior
        interior_idx.add(face)

    def add_interior_wire(self, occ_wire: cq.Wire, invert: bool = False):
        index_set = self.interior if not invert else self.exterior
        opp_index_set = self.exterior if not invert else self.interior
        index_set.add(occ_wire)
        for occ_edge in occ_wire.Edges():
            if occ_edge not in opp_index_set:
                index_set.add(occ_edge)
        for occ_vertex in occ_wire.Vertices():
            if occ_vertex not in opp_index_set:
                index_set.add(occ_vertex)

    def init_3d_objs(self, target: Union[cq.Workplane, Sequence[CQObject]]):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        for compound in cast(Sequence[cq.Solid], objs):
            for solid in compound.Solids():
                for shell in solid.Shells():
                    self.init_2d_objs(shell.Faces())
                    self.add_entity(shell)
                self.add_entity(solid)

    def init_2d_objs(self, target: Union[cq.Workplane, Sequence[CQObject]]):
        objs = target.vals() if isinstance(target, cq.Workplane) else target
        for occ_face in cast(Sequence[cq.Face], objs):
            for occ_wire in [occ_face.outerWire(), *occ_face.innerWires()]:
                for occ_edge in occ_wire.Edges():
                    for occ_vertex in occ_edge.Vertices():
                        self.add_entity(occ_vertex)
                    self.add_entity(occ_edge)
                self.add_entity(occ_wire)
            self.add_entity(occ_face)

    def add_entity(self, occ_obj: CQObject):
        entity_type = get_entity_type(occ_obj)
        registry = self.registries[entity_type]
        if occ_obj not in registry.entities:
            tag = len(registry.entities) + 1
            registry.entities[occ_obj] = Entity(entity_type, tag)


    def select_entity(self, occ_obj: CQObject):
        entity_type = get_entity_type(occ_obj)
        registry = self.registries[entity_type]
        return registry.entities[occ_obj]
    
    def select_entities(self, target: Union[cq.Workplane, Iterable[CQObject]], type: Optional[EntityType] = None):
        entities = OrderedSet[Entity]()
        occ_objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_occ_objs = occ_objs if type is None else select_occ_objs(occ_objs, type)
        for occ_obj in selected_occ_objs:
            try:
                selected_entity = self.select_entity(occ_obj)
                entities.add(selected_entity)
            except:
                ...

        return entities
    
    def select_batch_entities(self, target: Union[cq.Workplane, Iterable[CQObject]], parent_type: EntityType, child_type: EntityType):
        occ_objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_occ_batches = select_batch_occ_objs(occ_objs, parent_type, child_type)
        for selected_occ_batch in selected_occ_batches:
            yield self.select_entities(selected_occ_batch)