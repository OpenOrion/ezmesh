
from dataclasses import dataclass
import gmsh
from ezmesh.transaction import Context, Transaction


@dataclass
class RefineTransaction(Transaction):
    num_refines: int = 1

    def after_generation(self, ctx: Context):
        for _ in range(self.num_refines):
            gmsh.model.mesh.refine()

