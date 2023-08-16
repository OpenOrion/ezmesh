import gmsh
from dataclasses import dataclass
from typing import Literal, Sequence, Union
from ezmesh.entity import Entity, EntityTransaction, EntityType
from ezmesh.utils.types import OrderedSet

TransfiniteArrangementType = Literal["Left", "Right", "AlternateLeft", "AlternateRight"]
TransfiniteMeshType = Literal["Progression", "Bump"]

@dataclass(eq=False)
class SetTransfiniteEdge(EntityTransaction):
    entities: OrderedSet[Entity]
    "edges to be added to the boundary layer"

    node_counts: Sequence[int]
    "number per edge"

    mesh_types: Union[TransfiniteMeshType, Sequence[str]] = "Progression"
    "mesh type for each edge"

    coefs: Union[float, Sequence[float]] = 1.0
    "coefficients for each edge"


    def before_gen(self):
        for i, edge in enumerate(self.entities):
            assert edge.type == EntityType.edge, "SetTransfiniteEdge only accepts edges"
            mesh_type = self.mesh_types if isinstance(self.mesh_types, str) else self.mesh_types[i]
            coef = self.coefs[i] if isinstance(self.coefs, Sequence) else self.coefs
            gmsh.model.mesh.setTransfiniteCurve(edge.tag, self.node_counts[i]+1, mesh_type, coef)

@dataclass(eq=False)
class SetTransfiniteFace(EntityTransaction):
    entities: OrderedSet[Entity]
    "face to apply field"

    arrangement: TransfiniteArrangementType = "Left"
    "arrangement of transfinite face"

    def before_gen(self):
        for face in self.entities:
            assert face.type == EntityType.face, "SetTransfiniteFace only accepts faces"
            gmsh.model.mesh.setTransfiniteSurface(face.tag, self.arrangement)

@dataclass(eq=False)
class SetTransfiniteSolid(EntityTransaction):
    entities: OrderedSet[Entity]
    "face to apply field"

    def before_gen(self):
        for solid in self.entities:
            assert solid.type == EntityType.solid, "SetTransfiniteSolid only accepts solids"
            gmsh.model.mesh.setTransfiniteVolume(solid.tag)

