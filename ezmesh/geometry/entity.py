from dataclasses import field
import gmsh
import numpy as np
from typing import Any, Optional, Protocol, Sequence
from ezmesh.utils.types import DimType
from ezmesh.utils.types import Number, NumpyFloat


class MeshContext:
    point_tags: dict[tuple[Number, Number, Number], int]
    point_coords: dict[int, tuple[Number, Number, Number]]
    # edge_point_coods: dict[int, list[int]]
    edges: dict[int, Any]

    def __init__(self) -> None:
        self.point_tags = {}
        self.point_coords = {}
        self.edges = {}
        # self.edge_point_coods = {}

    def add_edge(self, edge):
        self.edges[edge.tag] = edge

    def add_point(self, tag: int, coord: tuple[Number, Number, Number]):
        self.point_tags[coord] = tag
        self.point_coords[tag] = coord

    def update(self):
        gmsh.model.mesh.generate(1)
        point_entities = gmsh.model.occ.getEntities(0)
        edge_entities = gmsh.model.occ.getEntities(1)

        node_tags, node_concatted, _ = gmsh.model.mesh.getNodes()
        point_tags = np.array([entity[1] for entity in point_entities], dtype=np.uint16)
        point_indices = np.argsort(point_tags-1)  # type: ignore
        point_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))[point_indices]

        # for (dim, edge_tag) in edge_entities:
        #     edge_concatted_elements = gmsh.model.mesh.getElements(dim, tag=edge_tag)
        #     edge_type, edge_node_tags_concatted = edge_concatted_elements[0][0], edge_concatted_elements[2][0]
        #     edge_node_tags = np.array(edge_node_tags_concatted, dtype=np.uint16).reshape((-1, 2))
        #     if edge_tag not in self.edge_point_coods:
        #         self.edge_point_coods[edge_tag] = []
        #     for (from_node_tag, to_node_tag) in edge_node_tags:
        #         if from_node_tag in point_tags and from_node_tag not in  self.edge_point_coods[edge_tag]:
        #             self.edge_point_coods[edge_tag].append(from_node_tag)
        #         if to_node_tag in point_tags and to_node_tag not in  self.edge_point_coods[edge_tag]:
        #             self.edge_point_coods[edge_tag].append(to_node_tag)

        for i, point_coord in enumerate(point_coords):
            self.point_tags[tuple(point_coord)] = point_indices[i]+1
            self.point_coords[point_indices[i]+1] = tuple(point_coord)

class GeoTransaction(Protocol):
    tag: Optional[int] = None
    "tag of entity"

    def before_sync(self, ctx: MeshContext) -> int:
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        ...

GeoEntityId = tuple[DimType, tuple[Number, Number, Number]]

class GeoEntity(GeoTransaction, Protocol):
    type: DimType
    "type of entity"

    label: Optional[str]
    "physical group label"        

    fields: Sequence = field(default_factory=list)
    "fields to be added to the surface"

    @property
    def center_of_mass(self):
        return tuple(round(x, 5) for x in gmsh.model.occ.getCenterOfMass(self.type.value, self.tag))

    @property
    def id(self) -> GeoEntityId:
        return (self.type, self.center_of_mass)