from typing import Optional, Sequence, Union
from cadquery.selectors import Selector
import gmsh
import cadquery as cq
from ezmesh.exporters import export_to_su2
from ezmesh.geometry.entity import DimType, GeoEntity, GeoEntityId, GeoTransaction, MeshContext
from ezmesh.geometry.field import Field
from ezmesh.geometry.plot import plot_entities
from ezmesh.geometry.volume import Volume
from ezmesh.mesh import Mesh
from ezmesh.utils.geometry import generate_mesh
from jupyter_cadquery import show

class Geometry:
    def __init__(self) -> None:
        self.ctx = MeshContext()

    def __enter__(self):
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def generate(self, transactions: Union[GeoTransaction, Sequence[GeoTransaction]]):
        self.mesh = generate_mesh(transactions, self.ctx)
        return self.mesh

    def write(self, filename: str):
        if filename.endswith(".su2"):
            export_to_su2(self.mesh, filename)
        else:
            gmsh.write(filename)




class GeometryQL:
    def __init__(self, target: Union[cq.Workplane, str]) -> None:
        self.workplane = cq.importers.importStep(target) if isinstance(target, str) else target
        self.file_path = target if isinstance(target, str) else "workplane.step"
        self.level = 0
        self.transactions = []
        self.mesh: Optional[Mesh] = None
        self.ctx = MeshContext()
        
        gmsh.initialize()
        if not isinstance(target, str) and self.file_path.endswith(".step"):
            cq.exporters.export(self.workplane, self.file_path)

        gmsh.open(self.file_path)
        gmsh.model.geo.synchronize()

        self.ctx.update() 
        self.register: dict[GeoEntityId, GeoEntity] = {}
        for (_, volume_tag) in gmsh.model.occ.getEntities(DimType.VOLUME.value):
            volume = Volume.from_tag(volume_tag, self.ctx)
            self.transactions.append(volume)
            self.register[volume.id] = volume
            for surface_loop in volume.surface_loops:
                for surface in surface_loop.surfaces:
                    self.register[surface.id] = surface
                    for curve_loop in surface.curve_loops:
                        for edge in curve_loop.edges:
                            self.register[edge.id] = edge

    def faces(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.faces(selector, tag)
        self.level += 1
        return self
    
    def edges(self, selector: Union[Selector, str, None] = None, tag: Union[str, None] = None):
        self.workplane = self.workplane.edges(selector, tag)
        self.level += 1
        return self

    def vertices(self, selector: Selector | str | None = None, tag: str | None = None):
        self.workplane = self.workplane.vertices(selector, tag)
        self.level += 1
        return self

    def vals(self) -> Sequence[GeoEntity]:
        cqobjects = self.workplane.vals()
        entities = []
        for cqobject in cqobjects:
            if isinstance(cqobject, (cq.occ_impl.shapes.Compound, cq.occ_impl.shapes.Solid)):
                type = DimType.VOLUME
            elif isinstance(cqobject, cq.occ_impl.shapes.Face):
                type = DimType.SURFACE
            elif isinstance(cqobject, cq.occ_impl.shapes.Edge):
                type = DimType.CURVE
            elif isinstance(cqobject, cq.occ_impl.shapes.Vertex):
                type = DimType.POINT
            else:
                raise ValueError(f"cannot get id for {cqobject}")

            if isinstance(cqobject, cq.occ_impl.shapes.Vertex):
                center_of_mass = tuple(round(x, 5) for x in (cqobject.X, cqobject.Y, cqobject.Z))
            else:
                center_of_mass =  tuple(round(x, 5) for x in cqobject.centerOfMass(cqobject).toTuple())
            id = (type, center_of_mass)
            entities.append(self.register[id])
        return entities
    
    def reset(self):
        self.workplane = self.workplane.end(self.level)
        self.level = 0

    def addPhysicalGroup(self, label: str):
        for entity in self.vals():
            entity.label = label
        self.reset()
        return self
    
    def addFields(self, fields: Sequence[Field]):
        for entity in self.vals():
            entity.fields = [*entity.fields, *fields]
        self.reset()
        return self

    def to_mesh(self):
        mesh = generate_mesh(self.vals(), self.ctx)
        self.reset()
        return mesh

    def write(self, filename: str):
        mesh = self.to_mesh()
        if filename.endswith(".su2"):
            export_to_su2(mesh, filename)
        else:
            gmsh.write(filename)
        return self

    def show(self):
        show(self.workplane)
        return self

    def plot(self):
        entities = self.vals()
        plot_entities(entities)
        return self

    def close(self):
        gmsh.finalize()
