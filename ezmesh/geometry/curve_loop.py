import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.entity import DimType, MeshContext, GeoTransaction
from ezmesh.geometry.edge import Curve, Edge, Line
from ezmesh.geometry.point import Point
from ezmesh.utils.types import NumpyFloat
from ezmesh.utils.geometry import get_group_name
from ezmesh.geometry.field import Field

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
class CurveLoop(GeoTransaction):
    edges: Sequence[Edge]
    "Lines of curve"

    label: Optional[str] = None
    "physical group label"

    fields: Sequence[Field] = field(default_factory=list)
    "fields to be added to the curve loop"

    tag: Optional[int] = None
    "tag of the curve loop when passing by reference"

    def __post_init__(self):
        super().__init__()
        self.dim_type = DimType.CURVE
        self.edge_groups: dict[str, list[Edge]] = {}
        

    def before_sync(self, ctx: MeshContext):
        edge_tags = [edge.before_sync(ctx) for edge in self.edges]
        self.tag = self.tag or gmsh.model.geo.add_curve_loop(edge_tags)
        
        self.edge_groups = {}
        for edge in self.edges:
            if edge.label:
                edge_group = get_group_name(edge.label)
                if edge_group not in self.edge_groups:
                    self.edge_groups[edge_group] = []
                self.edge_groups[edge_group].append(edge)
        # if self.label is None and len(self.edge_groups) == 1 and len(list(self.edge_groups.values())[0]) == len(self.edges):
        #     self.label = list(self.edge_groups.keys())[0]


        return self.tag

    def after_sync(self, ctx: MeshContext):
        # for edge in self.edges:
            # add physical groups here and account for duplicates
            # if edge.tag and edge.label:
            #     physical_group_id = (DimType.CURVE, edge.label)
            #     if physical_group_id in ctx.physical_groups:
            #         physical_group_tag = ctx.physical_groups[physical_group_id] 
            #         physical_group_tag = gmsh.model.remove_physical_groups(DimType.CURVE.value, [edge.tag])

            #     else:
            #         physical_group_tag = gmsh.model.add_physical_group(DimType.CURVE.value, [edge.tag])
            #         ctx.physical_groups[physical_group_id] = physical_group_tag

            #     gmsh.model.set_physical_name(DimType.CURVE.value, physical_group_tag, edge.label)


            # edge.after_sync(ctx)        

        for field in self.fields:
            field.after_sync(ctx, self)

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
        label: Optional[str] = None,
        fields: Sequence[Field] = [],
    ):
        groups = coordsOrGroups if isinstance(coordsOrGroups, Sequence) else [coordsOrGroups]
        group_labels = group_labels if group_labels else label
        
        edges: list[Edge] = []
        property_index = 0
        for i, group in enumerate(groups):
            if isinstance(group, np.ndarray):
                group_label = group_labels[property_index:] if isinstance(group_labels, list) else group_labels
                edges += get_lines(group, mesh_size, group_label)
                property_index += len(group)-1
            elif isinstance(group, tuple):
                type, coords = group
                group_label = group_labels[property_index] if isinstance(group_labels, list) else group_labels

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
                connector_label = group_labels[property_index] if isinstance(group_labels, list) else group_labels
                connector_line = Line(edges[-1].end, end_pnt, connector_label)
                edges.append(connector_line)
                property_index += 1

        return CurveLoop(edges, label, fields)
    
    def get_edges(self):
        return self.edges

    @staticmethod
    def from_tag(tag: int, edge_tags: Sequence[int], ctx: MeshContext):
        edges = [Edge.from_tag(edge_tag, ctx) for edge_tag in edge_tags]
        curve_loop = CurveLoop(edges, tag=tag)
        return curve_loop
    