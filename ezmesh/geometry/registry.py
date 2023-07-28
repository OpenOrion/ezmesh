from typing import Optional, Sequence, Union
from cadquery.selectors import Selector
import gmsh
import cadquery as cq
from ezmesh.geometry.entity import DimType, GeoEntity, GeoEntityId
from ezmesh.geometry.field import Field
from ezmesh.geometry.volume import Volume


class EntityRegistry():
    def __init__(self, workplane: cq.Workplane) -> None:
        self.workplane = workplane
        self.file_path =  "workplane.step" #TODO: make this a temp file
        cq.exporters.export(workplane, self.file_path)

        gmsh.initialize()    
        gmsh.open(self.file_path)
        gmsh.model.geo.synchronize()

        self.register: dict[GeoEntityId, GeoEntity] = {}
        for (_, volume_tag) in gmsh.model.occ.getEntities(DimType.VOLUME.value):
            volume = Volume.from_tag(volume_tag)
            self.register[volume.id] = volume
            for surface_loop in volume.surface_loops:
                for surface in surface_loop.surfaces:
                    self.register[surface.id] = surface
                    for curve_loop in surface.curve_loops:
                        for edge in curve_loop.edges:
                            self.register[edge.id] = edge
 
        gmsh.finalize()



    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.faces(selector, tag)
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.edges(selector, tag)
        return self

    def tag(self, name: str):
        self.workplane = self.workplane.tag(name)
        return self

    def get_id(self) -> GeoEntityId:
        cqobject = self.workplane.val()

        if isinstance(cqobject, cq.occ_impl.shapes.Compound):
            type = DimType.SURFACE
        elif isinstance(cqobject, cq.occ_impl.shapes.Face):
            type = DimType.SURFACE
        elif isinstance(cqobject, cq.occ_impl.shapes.Edge):
            type = DimType.CURVE
        else:
            raise ValueError(f"cannot get id for {cqobject}")

        center_of_mass =  tuple(round(x, 5) for x in cqobject.centerOfMass(cqobject).toTuple())
        return (type.value, center_of_mass)

    def addPhysicalGroup(self, label: str):
        id = self.get_id()
        self.register[id].label = label
        self.workplane = self.workplane.end()
        return self
    
    def addFields(self, fields: Sequence[Field]):
        id = self.get_id()
        entity = self.register[id]
        entity.fields = [*entity.fields, *fields]
        self.workplane = self.workplane.end()
        return self
