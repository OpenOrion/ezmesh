from typing import Sequence, Union
import gmsh
from ezmesh.geometry.transaction import Context, GeoTransaction, commit_geo_transactions
from ezmesh.mesh.importers import import_from_gmsh


class MeshTransaction:
    is_commited: bool = False
    "tag of entity"

    def before_gen(self):
        "completes transaction before mesh generation."
        ...

    def after_gen(self):
        "completes transaction after mesh generation."
        ...

def commit_mesh_transactions(transactions: Sequence[MeshTransaction], dim: int):
    for transaction in transactions:
        transaction.before_gen()

    gmsh.option.set_number("General.ExpertMode", 1)
    gmsh.model.mesh.generate(dim)

    for transaction in transactions:
        transaction.after_gen()
        transaction.is_commited = True


def generate_mesh(
    geo_transactions: Union[GeoTransaction, Sequence[GeoTransaction]], 
    mesh_transactions: Sequence[MeshTransaction] = [],
    ctx: Context = Context(), 
    dim: int = 3
):
    geo_transactions = [geo_transactions] if isinstance(geo_transactions, GeoTransaction) else geo_transactions
    commit_geo_transactions(geo_transactions, ctx)
    commit_mesh_transactions(mesh_transactions, dim)

    return import_from_gmsh()

