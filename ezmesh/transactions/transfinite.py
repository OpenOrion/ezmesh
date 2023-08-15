import gmsh
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from ezmesh.transactions.transaction import DimType, Entity, Transaction

@dataclass
class SetTransfiniteCurve(Transaction):
    curves: Iterable[Entity]
    "curves to be added to the boundary layer"

    node_counts: Sequence[int]
    "number per curve"

    mesh_types: Optional[Sequence[str]] = None
    "mesh type for each curve"

    coefs: Optional[Sequence[float]] = None
    "coefficients for each curve"

    def before_gen(self):
        for i, curve in enumerate(self.curves):
            assert curve.dim_type == DimType.CURVE, "SetTransfiniteCurve only accepts curves"
            mesh_type = self.mesh_types[i] if self.mesh_types is not None else "Progression"
            coef = self.coefs[i] if self.coefs is not None else 1.0
            gmsh.model.mesh.setTransfiniteCurve(curve.tag, self.node_counts[i]+1, mesh_type, coef)

@dataclass
class SetTransfiniteSurface(Transaction):
    surfaces: Iterable[Entity]
    "surface to apply field"

    arrangement: str = "Left"
    "arrangement of transfinite surface"

    def before_gen(self):
        for surface in self.surfaces:
            assert surface.dim_type == DimType.SURFACE, "SetTransfiniteSurface only accepts surfaces"
            gmsh.model.mesh.setTransfiniteSurface(surface.tag, self.arrangement)

@dataclass
class SetTransfiniteVolume(Transaction):
    volumes: Iterable[Entity]
    "surface to apply field"

    def before_gen(self):
        for volume in self.volumes:
            assert volume.dim_type == DimType.VOLUME, "SetTransfiniteVolume only accepts volumes"
            gmsh.model.mesh.setTransfiniteVolume(volume.tag)