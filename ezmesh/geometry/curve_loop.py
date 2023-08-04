import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union, cast
import numpy as np
import numpy.typing as npt
from ezmesh.utils.types import DimType
from ezmesh.geometry.transaction import MeshContext, GeoEntityTransaction
from ezmesh.geometry.edge import Curve, Edge, Line
from ezmesh.geometry.point import Point
from ezmesh.utils.types import NumpyFloat
from ezmesh.utils.geometry import get_group_name

GroupType = Union[npt.NDArray[NumpyFloat], tuple[str, npt.NDArray[NumpyFloat]]]

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
class CurveLoop(GeoEntityTransaction):
    edges: Sequence[Edge]
    "Lines of curve"

    label: Optional[str] = None
    "physical group label"

    tag: Optional[int] = None
    "tag of the curve loop when passing by reference"

    def __post_init__(self):
        self.type = DimType.CURVE

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

    def before_sync(self, ctx: MeshContext):
        edge_tags = [edge.before_sync(ctx) for edge in self.edges]
        self.tag = self.tag or gmsh.model.geo.add_curve_loop(edge_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        for edge in self.edges:
            edge.after_sync(ctx)        

    def get_exterior_coords(self, num_pnts: int):
        coords = [
            edge.get_coords(num_pnts)
            for edge in self.edges
        ]
        return np.concatenate(coords)


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
    
    def get_edges(self):
        return self.edges

    @staticmethod
    def from_tag(tag: int, edge_tags: Sequence[int], ctx: MeshContext):
        edges = [Edge.from_tag(edge_tag, ctx) for edge_tag in edge_tags]
        curve_loop = CurveLoop(edges, tag=tag)
        return curve_loop
    