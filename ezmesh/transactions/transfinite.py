import gmsh
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Sequence
from ezmesh.transactions.transaction import EntityType, Entity, Transaction

ArrangementType = Literal["Left", "Right", "AlternateLeft", "AlternateRight"]

@dataclass
class SetTransfiniteEdge(Transaction):
    edges: Iterable[Entity]
    "edges to be added to the boundary layer"

    node_counts: Sequence[int]
    "number per edge"

    mesh_types: Optional[Sequence[str]] = None
    "mesh type for each edge"

    coefs: Optional[Sequence[float]] = None
    "coefficients for each edge"

    def before_gen(self):
        self.edges = list(self.edges)
        for i, edge in enumerate(self.edges):
            assert edge.dim_type == EntityType.edge, "SetTransfiniteEdge only accepts edges"
            mesh_type = self.mesh_types[i] if self.mesh_types is not None else "Progression"
            coef = self.coefs[i] if self.coefs is not None else 1.0
            gmsh.model.mesh.setTransfiniteCurve(edge.tag, self.node_counts[i]+1, mesh_type, coef)

@dataclass
class SetTransfiniteFace(Transaction):
    faces: Iterable[Entity]
    "face to apply field"

    arrangement: ArrangementType = "Left"
    "arrangement of transfinite face"

    def before_gen(self):
        for face in self.faces:
            assert face.dim_type == EntityType.face, "SetTransfiniteFace only accepts faces"
            gmsh.model.mesh.setTransfiniteSurface(face.tag, self.arrangement)

@dataclass
class SetTransfiniteSolid(Transaction):
    solids: Iterable[Entity]
    "face to apply field"

    def before_gen(self):
        for solid in self.solids:
            assert solid.dim_type == EntityType.solid, "SetTransfiniteSolid only accepts solids"
            gmsh.model.mesh.setTransfiniteVolume(solid.tag)