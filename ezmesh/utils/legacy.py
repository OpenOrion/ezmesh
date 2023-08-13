from typing import Optional, Sequence, TypeVar, Union, cast
import numpy as np
import numpy.typing as npt
from ezmesh.geometry.transactions.curve_loop import CurveLoop
from ezmesh.geometry.transactions.curve import Curve
from ezmesh.geometry.transactions.point import Point
from ezmesh.utils.types import NumpyFloat

T = TypeVar('T')
PropertyType = Union[list[T], T, dict[str, T]]

GroupType = Union[npt.NDArray[NumpyFloat], tuple[str, npt.NDArray[NumpyFloat]]]

# def get_lines(coords: npt.NDArray[NumpyFloat], mesh_size: float, labels: Union[str, list[str], None] = None):
#     return [
#         Line(
#             start=Point(coords[i-1], mesh_size), 
#             end=Point(coords[i], mesh_size), 
#             label=labels[i-1] if isinstance(labels, list) else labels
#         )
#         for i in range(1, len(coords))
#     ]

# @property
# def edge_groups(curve_loop: CurveLoop):
#     edge_groups: dict[str, list[Edge]] = {}
#     for edge in curve_loop.curves:
#         if edge.label:
#             name = cast(str, get_group_name(edge.label))
#             if name not in edge_groups:
#                 edge_groups[name] = []
#             edge_groups[name].append(edge)
#     return edge_groups

# def get_group_name(selectors: Union[str, list[str]]):
#     group_names = []
#     for selector in (selectors if isinstance(selectors, list) else [selectors]):
#         if "/" in selector:
#             selector = selector.split("/")[0]
#         group_names.append(selector)
#     return group_names if len(group_names) > 1 else group_names[0]


# def get_property(property: Optional[Union[list[T], T, dict[str, T]]], index: int, label: Optional[str] = None, default: T = None) -> T:
#     if property is None:
#         return cast(T, default)
#     elif isinstance(property, list):
#         return property[index]
#     elif isinstance(property, dict):
#         if label is None:
#             return cast(T, default)
#         label_wildcard = f"{get_group_name(label)}/*"
#         if label in property:
#             return property[label]
#         elif label_wildcard in property:
#             return property[label_wildcard]
#         return cast(T, default)
#     else:
#         return property

# def curve_loop_from_coords(
#     coordsOrGroups: Union[npt.NDArray[NumpyFloat], Sequence[GroupType]],
#     mesh_size: float,
#     group_labels: Optional[Union[str, list[str]]] = None,
#     label: Optional[str] = None
# ):
#     groups = coordsOrGroups if isinstance(coordsOrGroups, Sequence) else [coordsOrGroups]
#     group_labels = group_labels if group_labels else label
    
#     edges: list[Edge] = []
#     property_index = 0
#     for i, group in enumerate(groups):
#         if isinstance(group, np.ndarray):
#             group_label = get_group_name(group_labels[property_index:] if isinstance(group_labels, list) else group_labels)
#             edges += get_lines(group, mesh_size, group_label)
#             property_index += len(group)-1
#         elif isinstance(group, tuple):
#             type, coords = group
#             group_label = get_group_name(group_labels[property_index] if isinstance(group_labels, list) else group_labels)

#             if type == "LineSegment":
#                 edges += get_lines(coords, mesh_size, group_label)
#             else:
#                 ctrl_pnts = [Point(ctrl_coord, mesh_size) for ctrl_coord in coords]
#                 if len(edges) > 1 and isinstance(edges[-1], Line):
#                     ctrl_pnts = [edges[-1].end, *ctrl_pnts]
#                 curve = Curve(ctrl_pnts, type, group_label)
#                 edges.append(curve)
#             property_index += 1

#         # Connect to first edge start point if last group otherwise use previous edge end point
#         end_pnt = edges[0].start if i == len(groups) - 1 else edges[-1].end
        
#         # Ignore repeat start/end point
#         if not np.all(edges[-1].end.coord == end_pnt.coord):
#             connector_label = get_group_name(group_labels[property_index] if isinstance(group_labels, list) else group_labels)
#             connector_line = Line(edges[-1].end, end_pnt, connector_label)
#             edges.append(connector_line)
#             property_index += 1

#     return CurveLoop(edges, label)


# @staticmethod
# def from_labels(surface: PlaneSurface, labels: tuple[str,str], curve_loop: Optional[CurveLoop] = None, arrangement: str = "Left"):
#     "create transfinite surface from edges"
    
#     # use primary curve loop of surface if curve loop is not defined
#     if curve_loop is None:
#         curve_loop = surface.curve_loops[0]

#     first_corner_group, second_corner_group = labels
#     corners = [
#         curve_loop.edge_groups[first_corner_group][0].start, 
#         curve_loop.edge_groups[first_corner_group][-1].end,
#         curve_loop.edge_groups[second_corner_group][0].start, 
#         curve_loop.edge_groups[second_corner_group][-1].end
#     ]

#     return TransfiniteSurfaceField(surface, corners, arrangement)
