import cadquery as cq
from cadquery.cq import CQObject
from typing import Iterable, Optional, Union
from ezmesh.occ import EntityType, OCCMap


class InteriorSelector(cq.Selector):
    def __init__(self, workplane: cq.Workplane, is_interior: bool = True):
        self.workplane = workplane
        self.is_interior = is_interior
    def filter(self, objectList):
        parent_objects = self.workplane.vals()
        if len(parent_objects) == 1 and isinstance(parent_objects[0], cq.Face): 
            return get_interior_edges(objectList[0], parent_objects[0], self.is_interior)
        return filter(lambda object: self.is_interior == get_interior_face(object), objectList)

def get_interior_face(object: cq.Face):
    face_normal = object.normalAt()
    face_centroid = object.Center()
    interior_dot_product = face_normal.dot(face_centroid)
    return interior_dot_product < 0

def get_interior_edges(object: Union[cq.Face, cq.Wire], parent: cq.Face, is_interior: bool):
    wires = parent.innerWires() if is_interior else [parent.outerWire()]
    if isinstance(object, cq.Wire): 
        return wires
    elif isinstance(object, cq.Edge):
        return [edge for  wire in wires for edge in wire.Edges()]

def get_selector(workplane: cq.Workplane, selector: Union[cq.Selector, str, None], is_interior: Optional[bool] = None):
    selectors = []
    if isinstance(selector, str):
        selector = selectors.append(cq.StringSyntaxSelector(selector))
    elif isinstance(selector, cq.Selector):
        selectors.append(selector)

    if is_interior is not None:
        selectors.append(InteriorSelector(workplane, is_interior))

    if len(selectors) > 0:
        prev_selector = selectors[0]
        for selector in selectors[1:]:
            prev_selector = cq.selectors.AndSelector(prev_selector, selector)
        return prev_selector

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
        workplane = workplane.extrude(-0.001).faces(">Z")

    return workplane

def tag_entities(workplane: cq.Workplane, ctx: OCCMap):
    "Tag all gmsh entity tags to workplane"
    for registry_name, registry in ctx.registries.items():
        for occ_obj in registry.entities.keys():
            tag = f"{registry_name}/{registry.entities[occ_obj].tag}"
            workplane.newObject([occ_obj]).tag(tag)

def get_tagged_occ_objs(workplane: cq.Workplane, tags: Union[str, Iterable[str]], type: EntityType):
    for tag in ([tags] if isinstance(tags, str) else tags):
        yield from select_occ_type(workplane._getTagged(tag), type)

def select_occ_type(workplane: cq.Workplane, type: EntityType):
    for val in workplane.vals():
        assert isinstance(val, cq.Shape), "target must be a shape"
        if type == "solid":
            yield from val.Solids()
        elif type == "shell":
            yield from val.Shells()
        elif type == "face":
            yield from val.Faces()
        elif type == "wire":
            yield from val.Wires()
        elif type == "edge":
            yield from val.Edges()
        elif type == "vertex":
            yield from val.Vertices()

def filter_occ_objs(occ_objs: Iterable[CQObject], filter_objs: Iterable[CQObject], is_included: bool):
    filter_objs = set(filter_objs)
    for occ_obj in occ_objs:
        if (is_included and occ_obj in filter_objs) or (not is_included and occ_obj not in filter_objs):
            yield occ_obj
