# from typing import Optional, Sequence, Union

# import numpy as np
# import numpy.typing as npt
# from ezmesh.geometry.curve_loop import CurveLoop
# from ezmesh.geometry.edge import Curve, Edge, Line
# from ezmesh.geometry.fields.field import Field
# from ezmesh.geometry.point import Point
# from ezmesh.utils.geometry import get_property

# from ezmesh.utils.types import NumpyFloat

# GroupType = Union[npt.NDArray[NumpyFloat], tuple[str, npt.NDArray[NumpyFloat]]]

# def curve_loop_from_coords(
#     coordsOrGroups: Union[npt.NDArray[NumpyFloat], list[GroupType]],
#     mesh_size: float,
#     curve_labels: Optional[Union[list[str], str]] = None,
#     label: Optional[str] = None,
#     fields: Sequence[Field] = [],
# ):
#     if curve_labels is None and label is not None:
#         curve_labels = label
    
#     groups = coordsOrGroups if isinstance(coordsOrGroups, list) else [coordsOrGroups]
#     edges: list[Edge] = []
#     property_index: int = 0

#     prev_point = None
#     first_point = None
#     for group in groups:
#         if isinstance(group, np.ndarray) or group[0] == "LineSegment":
            
#             coords = group if isinstance(group, np.ndarray) else group[1]
#             is_line_segment = isinstance(group, tuple)
            
#             for coord in coords:
#                 point = Point(coord, mesh_size)
#                 # adding lines to connect points
#                 if prev_point:
#                     curve_label = get_property(curve_labels, property_index)
#                     line = Line(prev_point, point, curve_label)
#                     edges.append(line)
#                     if not is_line_segment:
#                         property_index += 1

#                 if first_point is None:
#                     first_point = point
#                 prev_point = point
#             if is_line_segment:
#                 property_index += 1
#         else:
#             type, ctrl_coords = group
#             ctrl_points = [Point(ctrl_coord, mesh_size) for ctrl_coord in ctrl_coords]
#             if prev_point:
#                 if len(edges) > 1 and isinstance(edges[-1], Line):
#                     ctrl_points = [prev_point, *ctrl_points]
#                 else:
#                     line = Line(prev_point, ctrl_points[0], label=get_property(curve_labels, property_index))
#                     edges.append(line)
#                     property_index += 1

#             curve = Curve(ctrl_points, type, label=get_property(curve_labels, property_index))
#             edges.append(curve)
#             property_index += 1
            
#             prev_point = curve.ctrl_pnts[-1]
#             if first_point is None:
#                 first_point = curve.ctrl_pnts[0]

#     assert prev_point and first_point, "No points found in curve loop"

#     last_line = Line(prev_point, first_point, label=get_property(curve_labels, property_index))
#     edges.append(last_line)

#     return CurveLoop(edges, label, fields)