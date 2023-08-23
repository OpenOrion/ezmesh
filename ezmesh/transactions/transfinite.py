import gmsh
from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence

import numpy as np
from ezmesh.entity import Entity, EntityType
from ezmesh.transaction import SingleEntityTransaction
from ezmesh.utils.types import OrderedSet

TransfiniteArrangementType = Literal["Left", "Right", "AlternateLeft", "AlternateRight"]
TransfiniteMeshType = Literal["Progression", "Bump", "Beta"]

@dataclass(eq=False)
class SetTransfiniteEdge(SingleEntityTransaction):
    entity: Entity
    "edge to be added to the boundary layer"

    num_elems: int
    "number of elems for edge"

    mesh_type: TransfiniteMeshType = "Progression"
    "mesh type for edge"

    coef: float = 1.0
    "coefficients for edge"

    def __post_init__(self):
        super().__post_init__()
        self.num_nodes = self.num_elems + 1

    def before_gen(self):
        assert self.entity.type == EntityType.edge, "SetTransfiniteEdge only accepts edges"
        gmsh.model.mesh.setTransfiniteCurve(self.entity.tag, self.num_nodes, self.mesh_type, self.coef)


    def update_from_boundary_layer(
        self, 
        boundary_vertices: OrderedSet[Entity], 
        curr_vertices: OrderedSet[Entity],
        length: float,
        ratio: float,
        hwall_n: Optional[float] = None,
        num_layers: Optional[int] = None
    ):
        assert self.entity.type == EntityType.edge, "StructuredBoundaryLayer only accepts edges"
        if num_layers is None:
            assert hwall_n is not None, "hwall_n must be specified if num_layers is not specified"
            num_elems = np.log((hwall_n + length*ratio - length)/hwall_n)/np.log(ratio)
        else:
            num_elems = num_layers
        
        if curr_vertices.first in boundary_vertices and curr_vertices.last not in boundary_vertices:
            self.num_elems = num_elems
            self.coef = ratio
        elif curr_vertices.last in boundary_vertices and curr_vertices.first not in boundary_vertices:
            self.num_elems = num_elems
            self.coef = -ratio


@dataclass(eq=False)
class SetTransfiniteFace(SingleEntityTransaction):
    entity: Entity
    "face to apply field"

    arrangement: TransfiniteArrangementType = "Left"
    "arrangement of transfinite face"

    corners: OrderedSet[Entity] = field(default_factory=OrderedSet)
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

