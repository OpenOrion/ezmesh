import gmsh
from enum import Enum
from dataclasses import dataclass
from typing import Iterable, Literal
from ezmesh.utils.gmsh import EntityType
from ezmesh.transactions.transaction import Entity, Transaction

class MeshAlgorithm2D(Enum):
    MeshAdapt = 1
    Automatic = 2
    InitialMeshOnly = 3
    Delaunay = 5
    FrontalDelaunay = 6
    BAMG = 7
    FrontalDelaunayQuads = 8
    PackingOfParallelograms = 9
    QuasiStructuredQuad = 11

class MeshAlgorithm3D(Enum):
    Delaunay = 1
    InitialMeshOnly = 3
    Frontal = 4
    MMG3D = 7
    RTree = 9
    HXT = 10


MeshAlgorithm2DType =  Literal[
    "MeshAdapt",
    "Automatic",
    "InitialMeshOnly",
    "Delaunay",
    "FrontalDelaunay",
    "BAMG",
    "FrontalDelaunayQuads",
    "PackingOfParallelograms",
    "QuasiStructuredQuad"
]

MeshAlgorithm3DType =  Literal[
    "Delaunay",
    "InitialMeshOnly",
    "Frontal",
    "MMG3D", 
    "RTree", 
    "HXT"
]

@dataclass
class SetMeshAlgorithm(Transaction):
    entities: Iterable[Entity]
    "Entity to set algorithm for"

    type: MeshAlgorithm2DType
    "algorithm to use"

    per_face: bool = False
    "if True, set algorithm per face, otherwise for whole system"

    def before_gen(self):
        for entity in self.entities:
            if self.per_face:
                assert entity.dim_type == EntityType.face, "Can only set per face for edges"
                gmsh.model.mesh.setAlgorithm(entity.dim_type.value, entity.tag, MeshAlgorithm2D[self.type].value)
            else:
                algo_val = MeshAlgorithm2D[self.type].value
                gmsh.option.setNumber("Mesh.Algorithm", algo_val)


@dataclass
class SetMeshAlgorithm3D(Transaction):
    entities: Iterable[Entity]
    "Entity to set algorithm for"

    type: MeshAlgorithm3DType
    "algorithm to use"

    def before_gen(self):
        # for entity in self.entities:
        #     algo_val = MeshAlgorithm3D[self.type].value if isinstance(entity, Volume) else MeshAlgorithm2D[self.type].value
        #     gmsh.model.mesh.setAlgorithm(entity.type.value, entity.tag, algo_val)
        algo_val = MeshAlgorithm3D[self.type].value
        gmsh.option.setNumber("Mesh.Algorithm3D", algo_val)

