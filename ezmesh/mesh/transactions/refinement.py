import gmsh
from dataclasses import dataclass
from ezmesh.geometry.transaction import GeoEntity
from ezmesh.mesh.transaction import MeshTransaction


@dataclass
class Recombine(MeshTransaction):
    entity: GeoEntity
    "Entity to recombine for"

    angle: float = 45
    "Angle to recombine with"

    def after_gen(self):
        gmsh.model.mesh.setRecombine(self.entity.type.value, self.entity.tag, self.angle)

@dataclass
class SmoothTransaction(MeshTransaction):
    entity: GeoEntity
    "Entity to recombine for"
    
    num_smooths: int = 1
    "Number of times to smooth the mesh"

    def after_gen(self):
        gmsh.model.mesh.setSmoothing(self.entity.type.value, self.entity.tag, self.num_smooths)


@dataclass
class RefineTransaction(MeshTransaction):
    num_refines: int = 1
    "Number of times to refine the mesh"
    
    def after_gen(self):
        for _ in range(self.num_refines):
            gmsh.model.mesh.refine()

