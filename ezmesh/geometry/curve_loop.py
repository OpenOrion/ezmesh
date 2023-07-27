import gmsh
from dataclasses import dataclass, field
from typing import Optional, Sequence
import numpy as np
from ezmesh.geometry.entity import DimType, MeshContext, GeoEntity
from ezmesh.geometry.edge import Edge
from ezmesh.geometry.fields.field import Field
from ezmesh.utils.geometry import get_group_name


from typing import Optional, Sequence, Union

import numpy as np
import numpy.typing as npt
from ezmesh.geometry.edge import Curve, Edge, Line
from ezmesh.geometry.point import Point
from ezmesh.utils.geometry import get_property

from ezmesh.utils.types import NumpyFloat

GroupType = Union[npt.NDArray[NumpyFloat], tuple[str, npt.NDArray[NumpyFloat]]]

@dataclass
class CurveLoop(GeoEntity):
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

        for edge in self.edges:
            if edge.label:
                name = get_group_name(edge.label)
                if name not in self.edge_groups:
                    self.edge_groups[name] = []
                self.edge_groups[name].append(edge)


    def before_sync(self, ctx: MeshContext):
        edge_tags = [edge.before_sync(ctx) for edge in self.edges]
        self.tag = self.tag or gmsh.model.geo.add_curve_loop(edge_tags)
        return self.tag

    def after_sync(self, ctx: MeshContext):
        # NOTICE: No longer iterating Edges for after_sync 
        for field in self.fields:
            field.after_sync(ctx, self)

    def get_exterior_coords(self, num_pnts: int, is_cosine_sampling: bool = True):
        coords = [
            edge.get_coords(num_pnts, is_cosine_sampling)
            for edge in self.edges
        ]
        return np.concatenate(coords)


    @staticmethod
    def from_tag(tag: int, curve_tags: Sequence[int]):
        edges = []
        for curve_tag in curve_tags:
            edge = None
            edges.append(edge)
        
        curve_loop = CurveLoop(edges, tag=tag)
        return curve_loop
    


    @staticmethod
    def from_coords(
        coordsOrGroups: Union[npt.NDArray[NumpyFloat], list[GroupType]],
        mesh_size: float,
        curve_labels: Optional[Union[list[str], str]] = None,
        label: Optional[str] = None,
        fields: Sequence[Field] = [],
    ):
        if curve_labels is None and label is not None:
            curve_labels = label
        
        groups = coordsOrGroups if isinstance(coordsOrGroups, list) else [coordsOrGroups]
        edges: list[Edge] = []
        property_index: int = 0

        prev_point = None
        first_point = None
        for group in groups:
            if isinstance(group, np.ndarray) or group[0] == "LineSegment":
                
                coords = group if isinstance(group, np.ndarray) else group[1]
                is_line_segment = isinstance(group, tuple)
                
                for coord in coords:
                    point = Point(coord, mesh_size)
                    # adding lines to connect points
                    if prev_point:
                        curve_label = get_property(curve_labels, property_index)
                        line = Line(prev_point, point, curve_label)
                        edges.append(line)
                        if not is_line_segment:
                            property_index += 1

                    if first_point is None:
                        first_point = point
                    prev_point = point
                if is_line_segment:
                    property_index += 1
            else:
                type, ctrl_coords = group
                ctrl_points = [Point(ctrl_coord, mesh_size) for ctrl_coord in ctrl_coords]
                if prev_point:
                    if len(edges) > 1 and isinstance(edges[-1], Line):
                        ctrl_points = [prev_point, *ctrl_points]
                    else:
                        line = Line(prev_point, ctrl_points[0], label=get_property(curve_labels, property_index))
                        edges.append(line)
                        property_index += 1

                curve = Curve(ctrl_points, type, label=get_property(curve_labels, property_index))
                edges.append(curve)
                property_index += 1
                
                prev_point = curve.ctrl_pnts[-1]
                if first_point is None:
                    first_point = curve.ctrl_pnts[0]

        assert prev_point and first_point, "No points found in curve loop"

        last_line = Line(prev_point, first_point, label=get_property(curve_labels, property_index))
        edges.append(last_line)

        return CurveLoop(edges, label, fields)