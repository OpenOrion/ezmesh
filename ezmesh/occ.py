import cadquery as cq
from cadquery.cq import CQObject
from typing import Iterable, Literal, Optional, OrderedDict, Sequence, Union, cast
from ezmesh.utils.gmsh import EntityType
from ezmesh.transactions.transaction import Entity


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


def select_occ_objs(target: Union[cq.Workplane, Iterable[CQObject]], type: EntityType):
    occ_objs = target.vals() if isinstance(target, cq.Workplane) else target
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

def filter_occ_objs(occ_objs: Iterable[CQObject], filter_objs: Iterable[CQObject], is_included: bool):
    filter_objs = set(filter_objs)
    for occ_obj in occ_objs:
        if (is_included and occ_obj in filter_objs) or (not is_included and occ_obj not in filter_objs):
            yield occ_obj

class OCCRegistry:
    def __init__(self, dim_type: EntityType) -> None:
        self.dim_type = dim_type
        self.entities = OrderedDict[CQObject, Entity]()

class OCCMap:
    "Maps OCC objects to gmsh tags"
    def __init__(self, workplane: cq.Workplane) -> None:
        self.dimension = 2 if isinstance(workplane.val(), cq.Face) else 3

        self.registries: dict[EntityType, OCCRegistry] = {
            EntityType.solid: OCCRegistry(EntityType.solid),
            EntityType.shell: OCCRegistry(EntityType.shell),
            EntityType.face:  OCCRegistry(EntityType.face),
            EntityType.wire: OCCRegistry(EntityType.wire),
            EntityType.edge: OCCRegistry(EntityType.edge),
            EntityType.vertex: OCCRegistry(EntityType.vertex),
        }

        if self.dimension == 3:
            self._init_3d(workplane.vals())
        else:
            self._init_2d(workplane.vals())

    def _init_3d(self, objs: Sequence[CQObject]):
        for compound in cast(Sequence[cq.Solid], objs):
            for solid in compound.Solids():
                for shell in solid.Shells():
                    self._init_2d(shell.Faces())
                    self.add_entity(shell)
                self.add_entity(solid)

    def _init_2d(self, objs: Sequence[CQObject]):
        for occ_face in cast(Sequence[cq.Face], objs):
            for occ_wire in [occ_face.outerWire(), *occ_face.innerWires()]:
                for occ_edge in occ_wire.Edges():
                    for occ_vertex in occ_edge.Vertices():
                        self.add_entity(occ_vertex)
                    self.add_entity(occ_edge)
                self.add_entity(occ_wire)
            self.add_entity(occ_face)

    def get_registry(self, shape: CQObject):
        entity_type = get_entity_type(shape)
        return self.registries[entity_type]

    def add_entity(self, occ_obj: CQObject):
        registry = self.get_registry(occ_obj)
        if occ_obj not in registry.entities:
            tag = len(registry.entities) + 1
            registry.entities[occ_obj] = Entity(registry.dim_type, tag)

    def select_entity(self, occ_obj: CQObject):
        registry = self.get_registry(occ_obj)
        return registry.entities[occ_obj]
    
    def select_entities(self, target: Union[cq.Workplane, Iterable[CQObject]], type: Optional[EntityType] = None):
        occ_objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_occ_objs = occ_objs if type is None else select_occ_objs(occ_objs, type)
        for occ_obj in selected_occ_objs:
            try:
                yield self.select_entity(occ_obj)
            except:
                ...

    def select_batch_entities(self, target: Union[cq.Workplane, Iterable[CQObject]], parent_type: EntityType, child_type: EntityType):
        occ_objs = target.vals() if isinstance(target, cq.Workplane) else target
        selected_occ_batches = select_batch_occ_objs(occ_objs, parent_type, child_type)
        for selected_occ_batch in selected_occ_batches:
            yield self.select_entities(selected_occ_batch)