import gmsh
from dataclasses import dataclass, field
from typing import Literal, Sequence
from ezmesh.entity import Entity, SingleEntityTransaction, EntityType
from ezmesh.utils.types import OrderedSet

TransfiniteArrangementType = Literal["Left", "Right", "AlternateLeft", "AlternateRight"]
TransfiniteMeshType = Literal["Progression", "Bump", "Beta"]

@dataclass(eq=False)
class SetTransfiniteEdge(SingleEntityTransaction):
    entity: Entity
    "edge to be added to the boundary layer"

    node_count: int
    "number of nodes for edge"

    mesh_type: TransfiniteMeshType = "Progression"
    "mesh type for edge"

    coef: float = 1.0
    "coefficients for edge"

    def before_gen(self):
        assert self.entity.type == EntityType.edge, "SetTransfiniteEdge only accepts edges"
        gmsh.model.mesh.setTransfiniteCurve(self.entity.tag, self.node_count+1, self.mesh_type, self.coef)

@dataclass(eq=False)
class SetTransfiniteFace(SingleEntityTransaction):
    entity: Entity
    "face to apply field"

    arrangement: TransfiniteArrangementType = "Left"
    "arrangement of transfinite face"

    corners: OrderedSet[Entity] = field(default_factory=list)
    "corner point tags for transfinite face"

    def before_gen(self):
        assert self.entity.type == EntityType.face, "SetTransfiniteFace only accepts faces"
        corner_tags = [corner.tag for corner in self.corners]
        gmsh.model.mesh.setTransfiniteSurface(self.entity.tag, self.arrangement, corner_tags)

@dataclass(eq=False)
class SetTransfiniteSolid(SingleEntityTransaction):
    entity: Entity
    "face to apply field"

    def before_gen(self):
        assert self.entity.type == EntityType.solid, "SetTransfiniteSolid only accepts solids"
        gmsh.model.mesh.setTransfiniteVolume(self.entity.tag)

