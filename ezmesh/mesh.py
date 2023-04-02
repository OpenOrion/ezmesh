
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
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
class Mesh:
    dim: int
    elements: List[npt.NDArray[np.uint16]]
    element_types: List[ElementType]
    points: npt.NDArray[np.float64]
    markers: Dict[str, List[npt.NDArray[np.uint16]]]
    target_points: Dict[str, np.uint16] = field(default_factory=dict)

    def get_marker_length(self, marker_name: str):
        marker_length = 0
        for elements in self.markers[marker_name]:
            assert len(elements) == 2
            marker_length +=  np.linalg.norm(self.points[elements[0]] - self.points[elements[1]])
        return marker_length

    def add_target_point(self, target_name: str, marker_name: str, proportion: float):
        if marker_name not in self.markers:
            raise ValueError(f"Marker '{marker_name}' not found in mesh")
        if proportion < 0 or proportion > 1:
            raise ValueError(f"Proportion {proportion} must be in the range [0, 1]")
        total_marker_length = self.get_marker_length(marker_name)
        current_marker_length = 0
        for elements in self.markers[marker_name]:
            assert len(elements) == 2
            current_marker_length +=  np.linalg.norm(self.points[elements[0]] - self.points[elements[1]])
            if current_marker_length / total_marker_length >= proportion:
                self.target_points[target_name] = elements[0]
                return
        raise ValueError(f"Proportion {proportion} is too large for marker '{marker_name}'")