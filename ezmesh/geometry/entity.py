from dataclasses import field
import gmsh
import numpy as np
from typing import Any, Optional, Protocol, Sequence
from ezmesh.utils.types import DimType
from ezmesh.utils.types import Number, NumpyFloat


class MeshContext:
    point_tags: dict[tuple[Number, Number, Number], int]
    points: dict[int, Any]
    edges: dict[int, Any]

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.point_tags = {}
        self.points = {}
        self.edges = {}
        # self.edge_point_coods = {}

    def add_edge(self, edge):
        self.edges[edge.tag] = edge

    def add_point(self, point):
        self.point_tags[tuple(point.coord)] = point.tag
        self.points[point.tag] = point

    def get_edge_physical_groups(self):
        edge_physical_groups: dict[str, list[int]] = {}
        for edge in self.edges.values():
            if not edge.label or not edge.tag:
                continue
            if edge.label not in edge_physical_groups:
                edge_physical_groups[edge.label] = []
            edge_physical_groups[edge.label].append(edge.tag)
        return edge_physical_groups

    def update(self):
        gmsh.model.mesh.generate(1)
        point_entities = gmsh.model.occ.getEntities(0)
        edge_entities = gmsh.model.occ.getEntities(1)

        node_tags, node_concatted, _ = gmsh.model.mesh.getNodes()
        node_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))

        # TODO: for some reason some points are mission when getting directly from point entities
        # point_tags = np.argsort(np.array([entity[1] for entity in point_entities], dtype=np.uint16))
        # point_coords = np.array(node_concatted, dtype=NumpyFloat).reshape((-1, 3))[point_tags-1]

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

        from ezmesh.geometry.point import Point
        for i, point_coord in enumerate(node_coords):
            self.add_point(Point(point_coord, tag=node_tags[i]))

class GeoTransaction(Protocol):
    tag: Optional[int] = None
    "tag of entity"

    def before_sync(self, ctx: MeshContext) -> int:
        "completes transaction before syncronization and returns tag."
        ...

    def after_sync(self, ctx: MeshContext):
        "completes transaction after syncronization and returns tag."
        ...

GeoEntityId = tuple[DimType, tuple[float, float, float]]

def format_id(num: Number):
    return round(float(num), 5)

class GeoEntity(GeoTransaction, Protocol):
    type: DimType
    "type of entity"

    label: Optional[str]
    "physical group label"        

    fields: Sequence = field(default_factory=list)
    "fields to be added to the surface"

    @property
    def center_of_mass(self):
        return tuple(format_id(x) for x in gmsh.model.occ.getCenterOfMass(self.type.value, self.tag))

    @property
    def id(self) -> GeoEntityId:
        return (self.type, self.center_of_mass)