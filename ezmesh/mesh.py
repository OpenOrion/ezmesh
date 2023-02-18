
from dataclasses import dataclass
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
class Mesh:
    dim: int
    elements: List[npt.NDArray[np.uint16]]
    element_tags: List[np.uint16]
    element_types: List[ElementType]
    node_points: npt.NDArray[np.float64]
    node_tags: npt.NDArray[np.uint16]
    groups: Dict[str, npt.NDArray[np.uint16]]