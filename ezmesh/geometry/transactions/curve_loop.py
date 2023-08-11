import gmsh
from dataclasses import dataclass
from typing import Optional, Sequence, cast
import numpy as np
from ezmesh.geometry.transaction import Context, DimType, GeoEntity
from ezmesh.geometry.transactions.edge import Edge

@dataclass
class DirectedPath:
    edge: Edge
    "Edge of the path"

    direction: int = 1
    "Direction of the path. 1 for forward, -1 for backward"

    @property
    def end(self):
        return self.edge.end if self.direction == 1 else self.edge.start

    @property
    def start(self):
        return self.edge.start if self.direction == 1 else self.edge.end

def get_sorted_paths(edges: Sequence[Edge]):
    sorted_paths = [DirectedPath(edges[0], 1)]
    edges = list(edges[1:])
    while edges:
        for i, edge in enumerate(edges):
            if np.all(edge.start.coord == sorted_paths[-1].end.coord):
                directed_path = DirectedPath(edge, 1)
                sorted_paths.append(directed_path)
                edges.pop(i)
                break
            elif np.all(edge.end.coord == sorted_paths[-1].end.coord):
                directed_path = DirectedPath(edge, -1)
                sorted_paths.append(directed_path)
                edges.pop(i)
                break
            elif np.all(edge.start.coord == sorted_paths[0].start.coord):
                directed_path = DirectedPath(edge, -1)
                sorted_paths.insert(0, directed_path)
                edges.pop(i)
                break
        else:
            print("Warning: Edges do not form a closed loop")
            edges = []
    return sorted_paths


@dataclass
class CurveLoop(GeoEntity):
    edges: Sequence[Edge]
    "Lines of curve"

    label: Optional[str] = None
    "physical group label"

    tag: Optional[int] = None
    "tag of the curve loop when passing by reference"

    def __post_init__(self):
        self.type = DimType.CURVE_LOOP

    def set_label(self, label: str):
        for edge in self.edges:
            edge.set_label(label)
        super().set_label(label)

    def before_sync(self, ctx: Context):
        edge_tags = [
            sorted_path.direction*cast(int, sorted_path.edge.before_sync(ctx)) 
            for sorted_path in get_sorted_paths(self.edges)
        ]
        self.tag = self.tag or gmsh.model.geo.add_curve_loop(edge_tags)
        return self.tag

    def after_sync(self, ctx: Context):
        for edge in self.edges:
            edge.after_sync(ctx)        

    def get_coords(self, num_pnts: int = 20, is_cosine_sampling: bool = False):
        coord_groups = []
        for sorted_path in get_sorted_paths(self.edges):
            coord_group = sorted_path.edge.get_coords(num_pnts, is_cosine_sampling)
            if sorted_path.direction == -1:
                coord_group = coord_group[::-1]
            coord_groups.append(coord_group)
        return np.concatenate(coord_groups)

    @staticmethod
    def from_tag(tag: int, edge_tags: Sequence[int], ctx: Context):
        edges = [Edge.from_tag(edge_tag, ctx) for edge_tag in edge_tags]
        curve_loop = CurveLoop(edges, tag=tag)
        return curve_loop

 