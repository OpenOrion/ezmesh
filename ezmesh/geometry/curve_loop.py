import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union, cast
import numpy as np
import numpy.typing as npt
from ezmesh.utils.types import DimType
from ezmesh.geometry.transaction import GeoEntityId, MeshContext, GeoEntity, normalize_coord
from ezmesh.geometry.edge import Curve, Edge, Line
from ezmesh.geometry.point import Point
from ezmesh.utils.types import NumpyFloat
from ezmesh.utils.geometry import get_group_name

GroupType = Union[npt.NDArray[NumpyFloat], tuple[str, npt.NDArray[NumpyFloat]]]

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


def get_lines(coords: npt.NDArray[NumpyFloat], mesh_size: float, labels: Union[str, list[str], None] = None):
    return [
        Line(
            start=Point(coords[i-1], mesh_size), 
            end=Point(coords[i], mesh_size), 
            label=labels[i-1] if isinstance(labels, list) else labels
        )
        for i in range(1, len(coords))
    ]

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
    
    @property
    def edge_groups(self):
        edge_groups: dict[str, list[Edge]] = {}
        for edge in self.edges:
            if edge.label:
                name = cast(str, get_group_name(edge.label))
                if name not in edge_groups:
                    edge_groups[name] = []
                edge_groups[name].append(edge)
        return edge_groups

    def set_label(self, label: str):
        for edge in self.edges:
            edge.set_label(label)
        super().set_label(label)

    def before_sync(self, ctx: MeshContext):
        edge_tags = [
            sorted_path.direction*cast(int, sorted_path.edge.before_sync(ctx)) 
            for sorted_path in get_sorted_paths(self.edges)
        ]
        # edge_tags = [
        #     edge.before_sync(ctx) for edge in self.edges
        # ]
        self.tag = self.tag or gmsh.model.geo.add_curve_loop(edge_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
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
    def from_tag(tag: int, edge_tags: Sequence[int], ctx: MeshContext):
        edges = [Edge.from_tag(edge_tag, ctx) for edge_tag in edge_tags]
        curve_loop = CurveLoop(edges, tag=tag)
        return curve_loop

    @staticmethod
    def from_coords(
        coordsOrGroups: Union[npt.NDArray[NumpyFloat], Sequence[GroupType]],
        mesh_size: float,
        group_labels: Optional[Union[str, list[str]]] = None,
        label: Optional[str] = None
    ):
        groups = coordsOrGroups if isinstance(coordsOrGroups, Sequence) else [coordsOrGroups]
        group_labels = group_labels if group_labels else label
        
        edges: list[Edge] = []
        property_index = 0
        for i, group in enumerate(groups):
            if isinstance(group, np.ndarray):
                group_label = get_group_name(group_labels[property_index:] if isinstance(group_labels, list) else group_labels)
                edges += get_lines(group, mesh_size, group_label)
                property_index += len(group)-1
            elif isinstance(group, tuple):
                type, coords = group
                group_label = get_group_name(group_labels[property_index] if isinstance(group_labels, list) else group_labels)

                if type == "LineSegment":
                    edges += get_lines(coords, mesh_size, group_label)
                else:
                    ctrl_pnts = [Point(ctrl_coord, mesh_size) for ctrl_coord in coords]
                    if len(edges) > 1 and isinstance(edges[-1], Line):
                        ctrl_pnts = [edges[-1].end, *ctrl_pnts]
                    curve = Curve(ctrl_pnts, type, group_label)
                    edges.append(curve)
                property_index += 1

            # Connect to first edge start point if last group otherwise use previous edge end point
            end_pnt = edges[0].start if i == len(groups) - 1 else edges[-1].end
            
            # Ignore repeat start/end point
            if not np.all(edges[-1].end.coord == end_pnt.coord):
                connector_label = get_group_name(group_labels[property_index] if isinstance(group_labels, list) else group_labels)
                connector_line = Line(edges[-1].end, end_pnt, connector_label)
                edges.append(connector_line)
                property_index += 1

        return CurveLoop(edges, label)