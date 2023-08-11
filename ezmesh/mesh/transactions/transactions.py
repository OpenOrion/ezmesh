
from dataclasses import dataclass
import gmsh
from ezmesh.geometry.transaction import GeoTransaction, Context
from ezmesh.transaction import Context


@dataclass
class RefineTransaction(GeoTransaction):
    num_refines: int = 1

    def after_generation(self, ctx: Context):
        for _ in range(self.num_refines):
            gmsh.model.mesh.refine()


Mesh.Algorithm
2D mesh algorithm (1: MeshAdapt, 2: Automatic, 3: Initial mesh only, 5: Delaunay, 6: Frontal-Delaunay, 7: BAMG, 8: Frontal-Delaunay for Quads, 9: Packing of Parallelograms, 11: Quasi-structured Quad)
Default value: 6
Saved in: General.OptionsFileName

Mesh.Algorithm3D
3D mesh algorithm (1: Delaunay, 3: Initial mesh only, 4: Frontal, 7: MMG3D, 9: R-tree, 10: HXT)
Default value: 1
Saved in: General.OptionsFileName



@dataclass
class SetAlgoTransaction(GeoTransaction):
    num_refines: int = 1

    def after_generation(self, ctx: Context):
        for _ in range(self.num_refines):
            gmsh.model.mesh.setAlgorithm()