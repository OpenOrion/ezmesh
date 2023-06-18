
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List
import numpy.typing as npt
import numpy as np


class ElementType(Enum):
    LINE = 1
    TRIANGLE = 2
    QUADRILATERAL = 3
    TETRAHEDRON = 4
    HEXAHEDRON = 5
    PRISM = 6
    PYRAMID = 7
    POINT = 15


@dataclass
class BoundingBox:
    width: float
    height: float


@dataclass
class Mesh:
    dim: int
    elements: List[npt.NDArray[np.uint16]]
    element_types: List[ElementType]
    points: npt.NDArray[np.float64]
    markers: Dict[str, List[npt.NDArray[np.uint16]]]
    target_points: Dict[str, Dict[np.uint16, str]] = field(default_factory=dict)


    def get_bounding_box(self):
        max_point = self.points.min(axis=0)
        min_point = self.points.max(axis=0)
        return BoundingBox(width=max_point[0] - min_point[0], height=max_point[1] - min_point[1])

    def get_marker_length(self, marker_name: str):
        marker_length = 0
        for elements in self.markers[marker_name]:
            assert len(elements) == 2
            marker_length += np.linalg.norm(self.points[elements[0]] - self.points[elements[1]])
        return marker_length

    def get_marker_point(self, marker_name: str, proportion: float, as_index = False):
        if marker_name not in self.markers:
            raise ValueError(f"Marker '{marker_name}' not found in mesh")
        if proportion < 0 or proportion > 1:
            raise ValueError(f"Proportion {proportion} must be in the range [0, 1]")
        total_marker_length = self.get_marker_length(marker_name)
        current_marker_length = 0
        for point_indices in self.markers[marker_name]:
            assert len(point_indices) == 2
            current_marker_length += np.linalg.norm(self.points[point_indices[0]] - self.points[point_indices[1]])
            if current_marker_length / total_marker_length >= proportion:
                if as_index:
                    return point_indices[1]
                else:
                    return self.points[point_indices[1]]
        raise ValueError(f"Proportion {proportion} is too large for marker '{marker_name}'")

    def add_target_point(self, name: str, marker_name: str, proportion: float):
        point_index = self.get_marker_point(marker_name, proportion, as_index=True)
        if marker_name not in self.target_points:
            self.target_points[marker_name] = {}
        self.target_points[marker_name][point_index] = name
