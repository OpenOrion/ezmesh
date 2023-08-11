# Mesh.Algorithm
# 2D mesh algorithm (1: MeshAdapt, 2: Automatic, 3: Initial mesh only, 5: Delaunay, 6: Frontal-Delaunay, 7: BAMG, 8: Frontal-Delaunay for Quads, 9: Packing of Parallelograms, 11: Quasi-structured Quad)
# Default value: 6
# Saved in: General.OptionsFileName

# Mesh.Algorithm3D
# 3D mesh algorithm (1: Delaunay, 3: Initial mesh only, 4: Frontal, 7: MMG3D, 9: R-tree, 10: HXT)
# Default value: 1
# Saved in: General.OptionsFileName


from enum import Enum


class MeshAlgo2D(Enum):
    MeshAdapt = 1
    Automatic = 2
    InitialMeshOnly = 3
    Delaunay = 5
    FrontalDelaunay = 6
    BAMG = 7
    FrontalDelaunayQuads = 8
    PackingOfParallelograms = 9
    QuasiStructuredQuad = 11

class MeshAlgo3D(Enum):
    Delaunay = 1
    InitialMeshOnly = 3
    Frontal = 4
    MMG3D = 7
    RTree = 9
    HXT = 10


import gmsh
from dataclasses import dataclass
from ezmesh.geometry.transaction import GeoEntity
from ezmesh.transaction import Context, Transaction


@dataclass
class SetAlgoTransaction(Transaction):
    entity: GeoEntity
    "Entity to set algorithm for"
    
    num_refines: int = 1

    def after_generation(self, ctx: Context):
        for _ in range(self.num_refines):
            gmsh.model.mesh.setAlgorithm(self.entity.type.value, self.entity.tag, 1)