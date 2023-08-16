import gmsh
from typing import Callable, Union
from dataclasses import dataclass
from ezmesh.entity import Entity
from ezmesh.transaction import Transaction
from ezmesh.utils.types import OrderedSet

@dataclass
class Recombine(Transaction):
    entities: OrderedSet[Entity]
    "Entities to recombine for"

    angle: float = 45
    "Angle to recombine with"

    def before_gen(self):
        for entity in self.entities:
            gmsh.model.mesh.setRecombine(entity.type.value, entity.tag, self.angle)

@dataclass
class SetSmoothing(Transaction):
    entities: OrderedSet[Entity]
    "Entities to smooth for"
    
    num_smooths: int = 1
    "Number of times to smooth the mesh"

    def after_gen(self):
        for entity in self.entities:
            gmsh.model.mesh.setSmoothing(entity.type.value, entity.tag, self.num_smooths)


@dataclass
class Refine(Transaction):
    num_refines: int = 1
    "Number of times to refine the mesh"
    
    def after_gen(self):
        for _ in range(self.num_refines):
            gmsh.model.mesh.refine()

@dataclass
class SetMeshSize(Transaction):
    entities: OrderedSet[Entity]
    "Entities to set mesh sizes for"

    size: Union[float, Callable[[float, float, float], float]]
    "Size to set points"

    def before_gen(self):
        point_tags = [(entity.type.value, entity.tag) for entity in self.entities]
        if isinstance(self.size, float):
            gmsh.model.mesh.setSize(point_tags, self.size)
        else:
            gmsh.model.mesh.setSizeCallback(lambda dim, tag, x, y, z, lc: lc if tag in point_tags else self.size(x, y, z)) # type: ignore
