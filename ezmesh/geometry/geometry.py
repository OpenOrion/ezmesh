import gmsh
from typing import Sequence, Union
from ezmesh.exporters import export_to_su2
from ezmesh.geometry.entity import MeshContext, GeoTransaction
from ezmesh.importers import import_from_gmsh

class Geometry:
    def __enter__(self):
        self.ctx = MeshContext()
        gmsh.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        gmsh.finalize()

    def generate(self, transactions: Union[GeoTransaction, Sequence[GeoTransaction]]):
        if isinstance(transactions, Sequence):
            for transaction in transactions:
                transaction.before_sync(self.ctx)
        else:
            transactions.before_sync(self.ctx)
        gmsh.model.geo.synchronize()
        if isinstance(transactions, Sequence):
            for transaction in transactions:
                transaction.after_sync(self.ctx)
        else:
            transactions.after_sync(self.ctx)
        gmsh.option.set_number("General.ExpertMode", 1)
        gmsh.model.mesh.generate()
        self.mesh = import_from_gmsh()

        return self.mesh

    def write(self, filename: str):
        if filename.endswith(".su2"):
            export_to_su2(self.mesh, filename)
        else:
            gmsh.write(filename)
