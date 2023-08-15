import gmsh
from enum import Enum
from dataclasses import dataclass
from typing import Sequence
from ezmesh.gmsh import MeshAlgorithm2D, MeshAlgorithm2DType, MeshAlgorithm3D, MeshAlgorithm3DType
from ezmesh.transactions.transaction import Entity, Transaction

@dataclass
class SetMeshAlgorithm(Transaction):
    entities: Sequence[Entity]
    "Entity to set algorithm for"

    type: MeshAlgorithm2DType
    "algorithm to use"

    def before_gen(self):
        # for entity in self.entities:
        #     algo_val = MeshAlgorithm3D[self.type].value if isinstance(entity, Volume) else MeshAlgorithm2D[self.type].value
        #     gmsh.model.mesh.setAlgorithm(entity.type.value, entity.tag, algo_val)
        algo_val = MeshAlgorithm2D[self.type].value
        gmsh.option.setNumber("Mesh.Algorithm", algo_val)


@dataclass
class SetMeshAlgorithm3D(Transaction):
    entities: Sequence[Entity]
    "Entity to set algorithm for"

    type: MeshAlgorithm3DType
    "algorithm to use"

    def before_gen(self):
        # for entity in self.entities:
        #     algo_val = MeshAlgorithm3D[self.type].value if isinstance(entity, Volume) else MeshAlgorithm2D[self.type].value
        #     gmsh.model.mesh.setAlgorithm(entity.type.value, entity.tag, algo_val)
        algo_val = MeshAlgorithm3D[self.type].value
        gmsh.option.setNumber("Mesh.Algorithm3D", algo_val)
