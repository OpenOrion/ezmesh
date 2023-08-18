import gmsh
from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence, Union
from ezmesh.entity import Entity, EntityTransaction, EntityType
from ezmesh.utils.types import OrderedSet

TransfiniteArrangementType = Literal["Left", "Right", "AlternateLeft", "AlternateRight"]
TransfiniteMeshType = Literal["Progression", "Bump", "Beta"]

@dataclass(eq=False)
class SetTransfiniteEdge(EntityTransaction):
    entities: OrderedSet[Entity]
    "edges to be added to the boundary layer"

    node_counts: Union[Sequence[int], int]
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

            # if i > 0 and i < len(self.entities)-2:
            #     node_count = int(self.node_counts[1]/len(self.entities))
            # else:
            node_count = self.node_counts[i] if isinstance(self.node_counts, Sequence) else self.node_counts
            out = gmsh.model.occ.getCurveLoops(1)
            gmsh.model.mesh.setTransfiniteCurve(edge.tag, node_count+1, mesh_type, coef)

@dataclass(eq=False)
class SetTransfiniteFace(EntityTransaction):
    entities: OrderedSet[Entity]
    "face to apply field"

    arrangement: TransfiniteArrangementType = "Left"
    "arrangement of transfinite face"

    corner_tags: Sequence[int] = field(default_factory=list)
    "corner point tags for transfinite face"

    def before_gen(self):
        for face in self.entities:
            assert face.type == EntityType.face, "SetTransfiniteFace only accepts faces"
            gmsh.model.mesh.setTransfiniteSurface(face.tag, self.arrangement, self.corner_tags)

@dataclass(eq=False)
class SetTransfiniteSolid(EntityTransaction):
    entities: OrderedSet[Entity]
    "face to apply field"

    def before_gen(self):
        for solid in self.entities:
            assert solid.type == EntityType.solid, "SetTransfiniteSolid only accepts solids"
            gmsh.model.mesh.setTransfiniteVolume(solid.tag)

