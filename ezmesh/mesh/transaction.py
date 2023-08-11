from typing import Sequence, Union
import gmsh
from ezmesh.geometry.transaction import Context, GeoTransaction, commit_transactions
from ezmesh.mesh.importers import import_from_gmsh


class MeshTransaction:
    def after_gen(self):
        "completes transaction before syncronization and returns tag."
        ...

def generate_mesh(transactions: Union[GeoTransaction, Sequence[GeoTransaction]], dim: int = 3, ctx: Context = Context()):
    commit_transactions(transactions, ctx)
    gmsh.option.set_number("General.ExpertMode", 1)

    gmsh.model.mesh.generate(dim)
    
    return import_from_gmsh()

